"""Carga idempotente, aprovação de vínculo e as rotas, de ponta a ponta.

Sem configuração a suíte sobe o esquema num SQLite temporário, então roda sem container. O
produto roda em Postgres: com `ARCO_TEST_DATABASE_URL` apontando para um banco **descartável**,
a mesma suíte roda nele, e o esquema é derrubado e recriado a cada teste.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from arco_api import banco
from arco_api.carga import carregar, decidir, exportar, semear
from arco_api.modelos import (
    AMBIGUO,
    CASADO,
    ORIGEM_MODELO,
    PROPOSTO,
    PROVAVEL,
    REJEITADO,
    SEM_CANDIDATO,
    VALIDADO,
    Base,
    Restricao,
    RestricaoSnapshot,
    SerieRestricao,
    SimulacaoRevisao,
    Snapshot,
    VinculoRestricaoEquipamento,
)
from arco_api.mudancas import ORIGINAL
from arco_motor.premissas import PREMISSAS_PADRAO

RESTRICAO = "abc123def456"
SNAPSHOT = "2026-09-15"
OUTRO_SNAPSHOT = "2026-09-16"
OUTRA_RESTRICAO = "fff999aaa111"
EQUIPAMENTO = "CEJGII5ACT-1RN"


@pytest.fixture
def banco_vazio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Um banco limpo por teste, com o esquema criado a partir dos modelos."""
    url = os.environ.get("ARCO_TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'arco.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    banco._motores.clear()
    Base.metadata.drop_all(banco.motor(url))
    Base.metadata.create_all(banco.motor(url))
    return url


def _escrever_artefatos(
    pasta: Path, snapshot_id: str, restricao_id: str, *, solar: bool = False
) -> Path:
    """Artefatos mínimos, no formato que o preparo da feature 02 emite."""
    pasta.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    def instante(k: int) -> datetime:
        return datetime(2026, 1, 1, k // 2, 30 * (k % 2))

    serie = [(restricao_id, "eolica", instante(k), 100.0, 30, snapshot_id) for k in range(8)]
    if solar:
        # Solar só nas quatro primeiras meias horas, com potência e minutos diferentes dos da
        # eólica: é o que torna conferível a soma de `ambas` e a ponderação dos minutos.
        serie += [(restricao_id, "solar", instante(k), 40.0, 10, snapshot_id) for k in range(4)]

    def sql(valor: object) -> str:
        if valor is None:
            return "NULL"
        if isinstance(valor, bool):
            return "TRUE" if valor else "FALSE"
        if isinstance(valor, datetime):
            return f"TIMESTAMP '{valor}'"
        return repr(valor)

    capacidades = (
        "val_capacoperlongasemlimit, val_capacoperlongacomlimit, val_capacopercurtasemlimit,"
        " val_capacopercurtacomlimit, val_capacidadeoperveraodialonga,"
        " val_capacidadeoperveraonoitelonga, val_capacoperinvernodialonga,"
        " val_capacoperinvernonoitelonga, val_capacoperveradiacurta,"
        " val_capacoperveraonoitecurta, val_capacoperinvernodiacurta,"
        " val_capacoperinvernonoitecurta"
    )
    tabelas = {
        "restricoes": (
            "restricao_id, texto, origem, razao, nome_curto, contingencia,"
            " instrucao_operacao, energia_mwh, registros, snapshot_id",
            [
                (
                    restricao_id,
                    "LT 500 kV ACU III / JAGUARUANA II C1(V7)",
                    "LOC",
                    "CNF",
                    "LT 500 kV Açu III / Jaguaruana II · C1",
                    "LT 500 kV Açu III / Quixadá · C1",
                    "IO-ON.NE.5NE",
                    1000.0,
                    8,
                    snapshot_id,
                )
            ],
        ),
        "equipamentos": (
            "cod_equipamento, tensao_kv, subestacao_de, subestacao_para, num_barra_de,"
            f" num_barra_para, nome, proprietario, comprimento_km, {capacidades}, snapshot_id",
            [
                (
                    EQUIPAMENTO,
                    500,
                    "JAGUARUANA II",
                    "ACU III",
                    5924,
                    5350,
                    "LT 500 kV JAGUARUANA II / ACU III C V7",
                    "TAESA",
                    210.0,
                    3005.0,
                    3005.0,
                    4000.0,
                    4000.0,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    snapshot_id,
                )
            ],
        ),
        "subestacoes": (
            "nome, val_latitude, val_longitude, num_barra, val_niveltensao, snapshot_id",
            [("ACU III", -5.5, -36.9, 5350, 500.0, snapshot_id)],
        ),
        "serie": (
            "restricao_id, fonte, instante, corte_mw, minutos_cnf, snapshot_id",
            serie,
        ),
        "propostas_vinculo": (
            "restricao_id, cod_equipamento, candidatos, papel, alternativo, situacao, citacao,"
            " status, origem, snapshot_id",
            [
                (
                    restricao_id,
                    EQUIPAMENTO,
                    None,
                    "monitorado",
                    False,
                    "casado",
                    "500 kV ACU III / JAGUARUANA II C1(V7)",
                    PROPOSTO,
                    "parser",
                    snapshot_id,
                )
            ],
        ),
    }
    for nome, (colunas, linhas) in tabelas.items():
        valores = ", ".join("(" + ", ".join(sql(v) for v in linha) + ")" for linha in linhas)
        con.execute(
            f"COPY (SELECT * FROM (VALUES {valores}) AS t({colunas}))"
            f" TO '{pasta / f'{nome}.parquet'}' (FORMAT PARQUET)"
        )
    return pasta


@pytest.fixture
def artefatos(tmp_path: Path) -> Path:
    """O snapshot padrão dos testes, com uma restrição e um vínculo casado."""
    return _escrever_artefatos(tmp_path / "derivado", SNAPSHOT, RESTRICAO)


def test_carga_e_idempotente(banco_vazio: str, artefatos: Path) -> None:
    """Rodar duas vezes sobre o mesmo snapshot não duplica nada."""
    primeira = carregar(artefatos)
    segunda = carregar(artefatos)
    assert primeira.restricoes == segunda.restricoes == 1
    assert primeira.intervalos == segunda.intervalos == 8
    assert primeira.vinculos_novos == 1
    assert segunda.vinculos_novos == 0
    with banco.sessao() as s:
        assert len(list(s.scalars(select(Restricao)))) == 1
        assert len(list(s.scalars(select(VinculoRestricaoEquipamento)))) == 1


def test_vinculo_validado_nao_e_sobrescrito_pelo_parser(banco_vazio: str, artefatos: Path) -> None:
    """A assinatura do engenheiro vale mais que o parser, e sobrevive à carga seguinte."""
    carregar(artefatos)
    with banco.sessao() as s:
        alvo = s.scalars(select(VinculoRestricaoEquipamento)).one()
        vinculo_id = alvo.id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme", quando=date(2026, 9, 18))

    resumo = carregar(artefatos)
    assert resumo.vinculos_preservados == 1
    with banco.sessao() as s:
        alvo = s.get(VinculoRestricaoEquipamento, vinculo_id)
        assert alvo is not None
        assert alvo.status == VALIDADO
        assert alvo.validado_por == "Guilherme"


def test_rejeitado_nao_volta_a_proposto(banco_vazio: str, artefatos: Path) -> None:
    carregar(artefatos)
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, REJEITADO, validado_por="Thomas")
    carregar(artefatos)
    with banco.sessao() as s:
        assert s.get(VinculoRestricaoEquipamento, vinculo_id).status == REJEITADO  # type: ignore[union-attr]


def test_aprovar_exige_assinatura(banco_vazio: str, artefatos: Path) -> None:
    carregar(artefatos)
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    with pytest.raises(ValueError, match="exige o nome"):
        decidir(vinculo_id, VALIDADO, validado_por="   ")


def test_exportar_e_semear_refazem_a_curadoria(
    banco_vazio: str, artefatos: Path, tmp_path: Path
) -> None:
    """O banco é descartável: jogar fora e semear devolve os mesmos vínculos validados."""
    carregar(artefatos)
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme", quando=date(2026, 9, 18))

    semente = tmp_path / "vinculos_validados.csv"
    assert exportar(semente) == 1

    # Banco novo, do zero: carga do parser mais semeadura.
    outro = f"sqlite:///{tmp_path / 'outro.db'}"
    banco._motores.clear()
    Base.metadata.create_all(banco.motor(outro))
    carregar(artefatos, database_url=outro)
    assert semear(semente, database_url=outro) == 1
    with banco.sessao(outro) as s:
        alvo = s.scalars(select(VinculoRestricaoEquipamento)).one()
        assert (alvo.status, alvo.validado_por, alvo.validado_em) == (
            VALIDADO,
            "Guilherme",
            date(2026, 9, 18),
        )


@pytest.fixture
def cliente(banco_vazio: str, artefatos: Path) -> TestClient:
    from arco_api.main import app

    carregar(artefatos)
    return TestClient(app)


@pytest.fixture
def aprovado_com_solar(banco_vazio: str, tmp_path: Path) -> TestClient:
    """O mesmo snapshot com série solar ao lado da eólica, para exercitar `fonte=ambas`."""
    from arco_api.main import app

    carregar(_escrever_artefatos(tmp_path / "derivado", SNAPSHOT, RESTRICAO, solar=True))
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme")
    return TestClient(app)


PEDIDO_SIMULAR: dict[str, object] = {
    "restricao_id": RESTRICAO,
    "fonte": "eolica",
    "configuracao": {
        "modalidade": "equipamento",
        "equipamento": {
            "tipo": "adicao_circuito",
            "cod_equipamento": EQUIPAMENTO,
            "ganho_limite_mw": 40.0,
        },
        "financeira": {
            "cenario": "referencia",
            "taxa_desconto_aa": 0.08,
            "horizonte_anos": 15,
            "capex_reais": 1000.0,
        },
    },
}


def _reescreve_situacao(nova: str) -> None:
    """Troca a situação do vínculo carregado. O artefato da fixture nasce `casado`."""
    with banco.sessao() as s:
        alvo = s.scalars(select(VinculoRestricaoEquipamento)).one()
        alvo.situacao = nova
        s.commit()


def test_casado_entra_sem_assinatura(cliente: TestClient) -> None:
    """ADR 0008: quatro campos concordando contra o cadastro autorizam, e ninguém assinou nada.

    Antes desta regra o produto mostrava 1 restrição de 64, porque a fila de aprovação era
    pré-requisito até para o casamento em que não houve escolha nenhuma.
    """
    lista = cliente.get("/restricoes").json()
    assert [item["id"] for item in lista["itens"]] == [RESTRICAO]
    assert lista["resumo"]["restricoes"] == 1
    assert cliente.post("/simular", json=PEDIDO_SIMULAR).status_code == 200


@pytest.mark.parametrize("situacao", [PROVAVEL, AMBIGUO, SEM_CANDIDATO])
def test_casamento_duvidoso_nao_aparece_nem_simula(cliente: TestClient, situacao: str) -> None:
    """Onde o casamento chutou, fica de fora.

    Vínculo errado não estoura erro: vira capacidade errada, energia errada e VPL errado com
    cara de número bom. Falha de extração tem de sair como falha.
    """
    _reescreve_situacao(situacao)
    lista = cliente.get("/restricoes").json()
    assert lista["itens"] == []
    assert lista["resumo"]["restricoes"] == 0
    assert cliente.post("/simular", json=PEDIDO_SIMULAR).status_code == 409


def test_rejeitado_nao_entra_mesmo_casado(cliente: TestClient) -> None:
    """O veto de gente vale mais que a concordância do código."""
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, REJEITADO, validado_por="Thomas")
    assert cliente.get("/restricoes").json()["itens"] == []
    assert cliente.post("/simular", json=PEDIDO_SIMULAR).status_code == 409


def test_pessoa_valida_o_duvidoso_e_ele_passa_a_entrar(cliente: TestClient) -> None:
    """Quem olhou decide: validado entra de qualquer situação, inclusive das que o código recusa."""
    _reescreve_situacao(PROVAVEL)
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme")
    assert [item["id"] for item in cliente.get("/restricoes").json()["itens"]] == [RESTRICAO]


def test_nome_curto_contingencia_e_io_chegam_no_contrato(cliente: TestClient) -> None:
    """Os três vinham sempre `null` desde a feature 04. A tela mostrava texto cru truncado."""
    (item,) = cliente.get("/restricoes").json()["itens"]
    assert item["nome_curto"] == "LT 500 kV Açu III / Jaguaruana II · C1"
    assert item["contingencia"] == "LT 500 kV Açu III / Quixadá · C1"
    assert item["instrucao_operacao"] == "IO-ON.NE.5NE"

    detalhe = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert detalhe["nome_curto"] == item["nome_curto"]
    assert detalhe["contingencia"] == item["contingencia"]
    assert detalhe["instrucao_operacao"] == item["instrucao_operacao"]
    assert detalhe["texto"], "o texto do ONS continua lá, e nunca é nulo"


def test_nome_que_a_regra_nao_compos_fica_nulo_sem_inventar(
    banco_vazio: str, tmp_path: Path
) -> None:
    """Restrição sem nome mecânico cai no texto do ONS; a rota não inventa rótulo."""
    pasta = _escrever_artefatos(tmp_path / "derivado", SNAPSHOT, RESTRICAO)
    duckdb.connect().execute(
        f"COPY (SELECT * REPLACE (NULL AS nome_curto, NULL AS contingencia,"
        f" NULL AS instrucao_operacao) FROM '{pasta / 'restricoes.parquet'}')"
        f" TO '{pasta / 'restricoes.parquet'}' (FORMAT PARQUET)"
    )
    carregar(pasta)

    from arco_api.main import app

    (item,) = TestClient(app).get("/restricoes").json()["itens"]
    assert item["nome_curto"] is None
    assert item["instrucao_operacao"] is None
    assert item["texto"], "e o texto do ONS continua preenchido"


def test_carga_relata_o_que_entrou_e_o_que_saiu(
    banco_vazio: str, artefatos: Path, tmp_path: Path
) -> None:
    """Restrição que some não é erro; sumir calada é. O relatório é da task 13.2."""
    primeira = carregar(artefatos)
    assert primeira.restricoes_novas == [RESTRICAO]
    assert primeira.restricoes_sumidas == [], "não há snapshot anterior com que comparar"

    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme")

    segunda = carregar(
        _escrever_artefatos(tmp_path / "derivado-2", OUTRO_SNAPSHOT, OUTRA_RESTRICAO)
    )
    assert segunda.restricoes_novas == [OUTRA_RESTRICAO]
    (sumida,) = segunda.restricoes_sumidas
    assert sumida.restricao_id == RESTRICAO
    assert sumida.tinha_vinculo, "a que tinha assinatura sai destacada"
    assert [p[0] for p in sumida.parecidas] == [OUTRA_RESTRICAO], (
        "o texto é o mesmo nos dois artefatos, então a nova aparece como parecida"
    )


def test_recarregar_o_mesmo_snapshot_nao_acusa_sumico(banco_vazio: str, artefatos: Path) -> None:
    """Idempotência: rodar a carga duas vezes não pode inventar que a restrição sumiu."""
    carregar(artefatos)
    segunda = carregar(artefatos)
    assert segunda.restricoes_novas == []
    assert segunda.restricoes_sumidas == []


def test_identidade_da_restricao_sobrevive_ao_snapshot_novo(
    banco_vazio: str, artefatos: Path, tmp_path: Path
) -> None:
    """O ONS reescreve o texto, o `id` muda e a restrição antiga some do snapshot novo.

    Antes da [ADR 0009] isso apagava a restrição do banco e deixava vínculo, aviso, obra e
    simulação apontando para identificador inexistente, sem erro nenhum.
    """
    carregar(artefatos)
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme")

    carregar(_escrever_artefatos(tmp_path / "derivado-2", OUTRO_SNAPSHOT, OUTRA_RESTRICAO))

    with banco.sessao() as s:
        assert s.get(Restricao, RESTRICAO) is not None, "a identidade não se apaga"
        assert s.get(Restricao, OUTRA_RESTRICAO) is not None
        assert s.get(RestricaoSnapshot, (RESTRICAO, OUTRO_SNAPSHOT)) is None, (
            "a restrição antiga não foi medida no snapshot novo"
        )
        assert s.get(RestricaoSnapshot, (RESTRICAO, SNAPSHOT)) is not None, (
            "e a medição do snapshot antigo continua lá"
        )
        vinculo = s.get(VinculoRestricaoEquipamento, vinculo_id)
        assert vinculo is not None and vinculo.status == VALIDADO
        assert s.get(Restricao, vinculo.restricao_id) is not None, "o vínculo não ficou órfão"


def test_ranking_do_snapshot_novo_nao_traz_a_restricao_que_saiu(
    cliente: TestClient, tmp_path: Path
) -> None:
    assert [i["id"] for i in cliente.get("/restricoes").json()["itens"]] == [RESTRICAO]

    carregar(_escrever_artefatos(tmp_path / "derivado-2", OUTRO_SNAPSHOT, OUTRA_RESTRICAO))

    itens = [i["id"] for i in cliente.get("/restricoes").json()["itens"]]
    assert itens == [OUTRA_RESTRICAO], "o ranking é do snapshot ativo, e a antiga saiu dele"


def test_restricao_ausente_do_snapshot_responde_200_marcada(
    cliente: TestClient, tmp_path: Path
) -> None:
    """Task 13.3. `404` diria que a restrição não existe, e ela existe — só não foi medida.

    Uma simulação salva aponta para a identidade, então a página dela tem de continuar abrindo
    quando a restrição sai do snapshot ativo.
    """
    presente = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert presente["presente_no_snapshot"] is True
    assert presente["energia_mwh"] > 0

    carregar(_escrever_artefatos(tmp_path / "derivado-2", OUTRO_SNAPSHOT, OUTRA_RESTRICAO))

    resposta = cliente.get(f"/restricoes/{RESTRICAO}")
    assert resposta.status_code == 200, "a identidade existe; 404 seria mentira"
    ausente = resposta.json()
    assert ausente["presente_no_snapshot"] is False
    assert ausente["snapshot_id"] == OUTRO_SNAPSHOT
    assert ausente["texto"], "o primeiro texto visto continua rotulando a restrição"
    assert ausente["nome_curto"] == presente["nome_curto"], "a identidade não muda"


def test_restricao_ausente_nao_traz_numero_de_outro_snapshot(
    cliente: TestClient, tmp_path: Path
) -> None:
    """Pior que não mostrar número é mostrar o número errado com cara de certo."""
    carregar(_escrever_artefatos(tmp_path / "derivado-2", OUTRO_SNAPSHOT, OUTRA_RESTRICAO))

    ausente = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert ausente["energia_mwh"] == 0.0
    assert ausente["fatia_do_total"] == 0.0
    assert ausente["fontes"] == []

    serie = cliente.get(f"/restricoes/{RESTRICAO}/serie").json()
    assert serie["pontos"] == [], "sem medição no snapshot ativo, a série é vazia, não de antes"


def test_identidade_que_nunca_existiu_continua_404(cliente: TestClient) -> None:
    assert cliente.get("/restricoes/naoexiste123").status_code == 404


def test_simulacao_salva_nao_perde_o_texto_quando_a_restricao_sai(
    cliente: TestClient, tmp_path: Path
) -> None:
    """`restricao_texto` vinha `null` quando a restrição não estava no snapshot da revisão."""
    pedido = dict(PEDIDO, nome="Reforço do circuito")
    assert cliente.post("/simulacoes", json=pedido).status_code == 200

    carregar(_escrever_artefatos(tmp_path / "derivado-2", OUTRO_SNAPSHOT, OUTRA_RESTRICAO))

    (item,) = cliente.get("/simulacoes").json()
    assert item["restricao_id"] == RESTRICAO
    assert item["restricao_texto"] is not None, "a identidade guarda o texto, então ele não some"


def _torna_ambiguo(candidatos: str) -> int:
    """Reescreve o vínculo como proposta ambígua: sem código escolhido, com candidatos."""
    with banco.sessao() as s:
        alvo = s.scalars(select(VinculoRestricaoEquipamento)).one()
        alvo.situacao = AMBIGUO
        alvo.cod_equipamento = None
        alvo.candidatos = candidatos
        s.commit()
        return alvo.id


def test_procedencia_diz_o_que_sustenta_o_vinculo(cliente: TestClient) -> None:
    """Procedência não é `status`: é o apoio que o número tem, para a tela poder dizer."""
    detalhe = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert detalhe["equipamentos"][0]["procedencia"] == "automatica"

    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme")

    detalhe = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert detalhe["equipamentos"][0]["procedencia"] == "por_pessoa"


def test_procedencia_de_modelo_se_distingue_da_automatica(cliente: TestClient) -> None:
    """O que a feature 08 produzir aparece como modelo, não como casamento determinístico."""
    with banco.sessao() as s:
        alvo = s.scalars(select(VinculoRestricaoEquipamento)).one()
        alvo.origem = ORIGEM_MODELO
        s.commit()
    detalhe = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert detalhe["equipamentos"][0]["procedencia"] == "por_modelo"


def test_aprovar_ambiguo_sem_escolher_recusa(cliente: TestClient) -> None:
    """Antes, isso gravava `validado` com código nulo, que a rota descarta calada."""
    vinculo_id = _torna_ambiguo(f"{EQUIPAMENTO}|OUTRO-5XXX-1")
    with pytest.raises(ValueError, match="exige escolher"):
        decidir(vinculo_id, VALIDADO, validado_por="Guilherme")
    assert cliente.get("/restricoes").json()["itens"] == []


def test_aprovar_ambiguo_escolhendo_poe_a_restricao_no_ranking(cliente: TestClient) -> None:
    vinculo_id = _torna_ambiguo(f"{EQUIPAMENTO}|OUTRO-5XXX-1")
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme", cod_equipamento=EQUIPAMENTO)

    assert [i["id"] for i in cliente.get("/restricoes").json()["itens"]] == [RESTRICAO]
    detalhe = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert detalhe["equipamentos"][0]["cod_equipamento"] == EQUIPAMENTO
    assert detalhe["equipamentos"][0]["procedencia"] == "por_pessoa"


def test_escolha_fora_dos_candidatos_recusa(cliente: TestClient) -> None:
    """Desempatar é escolher entre o que o casamento achou, não digitar um código qualquer."""
    vinculo_id = _torna_ambiguo(f"{EQUIPAMENTO}|OUTRO-5XXX-1")
    with pytest.raises(ValueError, match="não está entre os candidatos"):
        decidir(vinculo_id, VALIDADO, validado_por="Guilherme", cod_equipamento="INVENTADO-1")


def test_escolha_que_duplicaria_outro_vinculo_recusa(cliente: TestClient) -> None:
    """Dois vínculos da mesma restrição não podem apontar para o mesmo equipamento e papel."""
    vinculo_id = _torna_ambiguo(f"{EQUIPAMENTO}|OUTRO-5XXX-1")
    with banco.sessao() as s:
        s.add(
            VinculoRestricaoEquipamento(
                restricao_id=RESTRICAO,
                cod_equipamento=EQUIPAMENTO,
                papel="monitorado",
                situacao=CASADO,
                status=PROPOSTO,
                origem="parser",
            )
        )
        s.commit()
    with pytest.raises(ValueError, match="já é vínculo"):
        decidir(vinculo_id, VALIDADO, validado_por="Guilherme", cod_equipamento=EQUIPAMENTO)


def test_rejeitar_ambiguo_nao_exige_escolha(cliente: TestClient) -> None:
    """Rejeitar é sobre a proposta inteira: não há o que desempatar."""
    vinculo_id = _torna_ambiguo(f"{EQUIPAMENTO}|OUTRO-5XXX-1")
    decidir(vinculo_id, REJEITADO, validado_por="Thomas")
    with banco.sessao() as s:
        assert s.get(VinculoRestricaoEquipamento, vinculo_id).status == REJEITADO  # type: ignore[union-attr]


def test_fluxo_completo_da_restricao_ao_calculo(cliente: TestClient) -> None:
    """Da restrição ao cálculo sem ninguém aprovar nada: quem autoriza é a conferência."""
    lista = cliente.get("/restricoes").json()["itens"]
    assert [r["id"] for r in lista] == [RESTRICAO]
    assert lista[0]["equipamentos"] == 1

    detalhe = cliente.get(f"/restricoes/{RESTRICAO}").json()
    assert detalhe["equipamentos"][0]["cod_equipamento"] == EQUIPAMENTO
    assert detalhe["equipamentos"][0]["papel"] == "monitorado"

    serie = cliente.get(f"/restricoes/{RESTRICAO}/serie").json()
    assert len(serie["pontos"]) == 8

    pedido = {
        "restricao_id": RESTRICAO,
        "fonte": "eolica",
        "nome": "Circuito novo — referência",
        "configuracao": {
            "modalidade": "equipamento",
            "equipamento": {
                "tipo": "adicao_circuito",
                "cod_equipamento": EQUIPAMENTO,
                "ganho_limite_mw": 40.0,
            },
            "financeira": {
                "cenario": "referencia",
                "taxa_desconto_aa": 0.08,
                "horizonte_anos": 15,
                "capex_reais": 1000.0,
                "preco_energia_reais_mwh": 216.0,
            },
        },
    }
    calculado = cliente.post("/simular", json=pedido).json()
    assert calculado["tecnico"]["energia_evitada_equipamento_mwh"] == pytest.approx(160.0)
    assert "sensibilidade_equipamento" in calculado["premissas_usadas"]

    salvo = cliente.post("/simulacoes", json=pedido).json()
    assert salvo["metodo_versao"] == calculado["metodo_versao"]

    revisao = {k: v for k, v in pedido.items() if k != "restricao_id"}
    revisao["simulacao_id"] = salvo["simulacao_id"]
    nova = cliente.post("/simulacoes", json=revisao).json()
    assert nova["simulacao_id"] == salvo["simulacao_id"]
    assert nova["revisao_anterior_id"] == salvo["id"]
    listagem = cliente.get("/simulacoes").json()
    assert len(listagem) == 1, "duas revisões da mesma simulação são um item, não dois"
    assert [revisao["posicao"] for revisao in listagem[0]["revisoes"]] == [2, 1]

    inteira = cliente.get(f"/simulacoes/{salvo['id']}").json()
    assert inteira["resultado"]["tecnico"]["energia_cortada_mwh"] == pytest.approx(400.0)
    assert "autor" not in salvo
    assert "autor" not in inteira


@pytest.fixture
def aprovado(cliente: TestClient) -> TestClient:
    with banco.sessao() as s:
        vinculo_id = s.scalars(select(VinculoRestricaoEquipamento)).one().id
    decidir(vinculo_id, VALIDADO, validado_por="Guilherme")
    return cliente


def test_snapshot_declara_a_janela(aprovado: TestClient) -> None:
    """Sem janela no artefato a rota diz `null`; com janela, conta as meias horas dela."""
    sem_janela = aprovado.get("/snapshot").json()
    assert sem_janela["id"] == SNAPSHOT
    assert sem_janela["meias_horas_no_periodo"] is None

    with banco.sessao() as s:
        snapshot = s.get(Snapshot, SNAPSHOT)
        assert snapshot is not None
        snapshot.periodo_inicio = datetime(2025, 9, 1)
        snapshot.periodo_fim = datetime(2026, 9, 1)
        s.commit()
    assert aprovado.get("/snapshot").json()["meias_horas_no_periodo"] == 17520


def test_lista_traz_resumo_fatia_e_ocorrencias(aprovado: TestClient) -> None:
    lista = aprovado.get("/restricoes").json()
    # A energia é a da série na fonte pedida: 8 meias horas de 100 MW.
    assert lista["resumo"] == {
        "fonte": "eolica",
        "snapshot_id": SNAPSHOT,
        "restricoes": 1,
        "energia_mwh": pytest.approx(400.0),
        # O invariante manda aviso visível, e a premissa da contagem está `proposta`: a lista
        # carrega o limite junto do número, não só na descrição do campo no OpenAPI.
        "aviso_ocorrencias": lista["resumo"]["aviso_ocorrencias"],
    }
    assert "auditoria" in lista["resumo"]["aviso_ocorrencias"]
    item = lista["itens"][0]
    assert item["posicao"] == 1
    assert item["energia_mwh"] == pytest.approx(400.0)
    assert item["fatia_do_total"] == pytest.approx(1.0)
    assert item["subestacoes"] == ["ACU III", "JAGUARUANA II"]
    # Nome e Instrução de Operação chegaram com a feature 10; a contagem de ocorrências, com a
    # 07. As 8 meias horas do fixture são seguidas, então são um episódio só.
    assert item["nome_curto"] == "LT 500 kV Açu III / Jaguaruana II · C1"
    assert item["instrucao_operacao"] == "IO-ON.NE.5NE"
    assert item["ocorrencias"] == 1


def test_ocorrencias_abrem_para_auditoria(aprovado: TestClient) -> None:
    """As 8 meias horas do fixture, de 00:00 a 03:30 em 100 MW, são uma ocorrência de 4 h."""
    corpo = aprovado.get(f"/restricoes/{RESTRICAO}/ocorrencias").json()

    assert corpo["total"] == 1
    assert corpo["energia_mwh"] == pytest.approx(400.0)
    assert "auditoria" in corpo["aviso"]
    unica = corpo["itens"][0]
    assert unica["inicio"] == "2026-01-01T00:00:00"
    assert unica["fim"] == "2026-01-01T04:00:00"
    assert unica["intervalos"] == 8
    assert unica["duracao_horas"] == pytest.approx(4.0)
    assert unica["corte_medio_maximo_mw"] == pytest.approx(100.0)


def test_ocorrencias_fecham_com_a_energia_da_restricao(aprovado: TestClient) -> None:
    detalhe = aprovado.get(f"/restricoes/{RESTRICAO}").json()
    corpo = aprovado.get(f"/restricoes/{RESTRICAO}/ocorrencias").json()

    assert corpo["energia_mwh"] == pytest.approx(detalhe["energia_mwh"])
    assert corpo["total"] == len(corpo["itens"])


def test_ocorrencias_sem_serie_na_fonte_respondem_vazio(aprovado: TestClient) -> None:
    """Não ter cortado nesta fonte é fato sobre a restrição, não restrição inexistente."""
    corpo = aprovado.get(f"/restricoes/{RESTRICAO}/ocorrencias", params={"fonte": "solar"})

    assert corpo.status_code == 200
    assert corpo.json()["itens"] == []
    assert corpo.json()["total"] == 0
    assert corpo.json()["energia_mwh"] == 0


def test_fonte_sem_corte_tira_a_restricao_do_ranking(aprovado: TestClient) -> None:
    solar = aprovado.get("/restricoes", params={"fonte": "solar"}).json()
    assert solar["itens"] == []
    assert solar["resumo"]["energia_mwh"] == 0
    assert aprovado.get("/restricoes", params={"fonte": "vento"}).status_code == 422


def test_pagina_da_restricao(aprovado: TestClient) -> None:
    detalhe = aprovado.get(f"/restricoes/{RESTRICAO}").json()
    assert detalhe["fontes"] == ["eolica"]
    assert detalhe["energia_mwh"] == pytest.approx(400.0)
    assert detalhe["fatia_do_total"] == pytest.approx(1.0)
    assert detalhe["subestacoes"] == ["ACU III", "JAGUARUANA II"]
    assert detalhe["avisos"] == []
    assert detalhe["nome_curto"] == "LT 500 kV Açu III / Jaguaruana II · C1"
    assert detalhe["contingencia"] == "LT 500 kV Açu III / Quixadá · C1"
    assert detalhe["instrucao_operacao"] == "IO-ON.NE.5NE"
    assert detalhe["equipamentos"][0]["proprietario"] == "TAESA"
    assert detalhe["equipamentos"][0]["capacidade_longa_mva"] == 3005.0


@pytest.mark.parametrize(("agregacao", "baldes"), [("dia", 31), ("semana", 5), ("mes", 1)])
def test_serie_agregada_fecha_com_a_energia(
    aprovado: TestClient, agregacao: str, baldes: int
) -> None:
    """Balde sem corte volta zerado dentro da janela, e a soma é a energia da restrição."""
    with banco.sessao() as s:
        snapshot = s.get(Snapshot, SNAPSHOT)
        assert snapshot is not None
        snapshot.periodo_inicio = datetime(2026, 1, 1)
        snapshot.periodo_fim = datetime(2026, 2, 1)
        s.commit()
    serie = aprovado.get(f"/restricoes/{RESTRICAO}/serie", params={"agregacao": agregacao}).json()
    assert serie["pontos"] == []
    assert len(serie["baldes"]) == baldes
    assert sum(b["energia_mwh"] for b in serie["baldes"]) == pytest.approx(400.0)
    assert sum(1 for b in serie["baldes"] if b["energia_mwh"] > 0) == 1


def test_serie_crua_continua_a_de_antes(aprovado: TestClient) -> None:
    serie = aprovado.get(f"/restricoes/{RESTRICAO}/serie").json()
    assert serie["agregacao"] == "meia_hora"
    assert len(serie["pontos"]) == 8
    assert serie["baldes"] == []


def test_simulacoes_filtram_por_restricao(aprovado: TestClient) -> None:
    pedido = {
        "restricao_id": RESTRICAO,
        "nome": "Circuito novo",
        "configuracao": {
            "modalidade": "equipamento",
            "equipamento": {
                "tipo": "adicao_circuito",
                "cod_equipamento": EQUIPAMENTO,
                "ganho_limite_mw": 40.0,
            },
            "financeira": {
                "cenario": "referencia",
                "taxa_desconto_aa": 0.08,
                "horizonte_anos": 15,
                "capex_reais": 1000.0,
            },
        },
    }
    assert aprovado.post("/simulacoes", json=pedido).status_code == 200
    assert len(aprovado.get("/simulacoes", params={"restricao_id": RESTRICAO}).json()) == 1
    assert aprovado.get("/simulacoes", params={"restricao_id": "outra"}).json() == []


FINANCEIRA: dict[str, object] = {
    "cenario": "referencia",
    "taxa_desconto_aa": 0.08,
    "horizonte_anos": 15,
    "capex_reais": 1000.0,
}

PEDIDO: dict[str, object] = {
    "restricao_id": RESTRICAO,
    "nome": "Circuito novo",
    "configuracao": {
        "modalidade": "equipamento",
        "equipamento": {
            "tipo": "adicao_circuito",
            "cod_equipamento": EQUIPAMENTO,
            "ganho_limite_mw": 40.0,
        },
        "financeira": FINANCEIRA,
    },
}


def _revisao_de(salva: dict) -> dict[str, object]:  # type: ignore[type-arg]
    """O pedido de uma revisão: pela simulação, e **sem** `restricao_id`.

    A restrição é da simulação, não da revisão. Mandar as duas permitia calcular com a série de
    uma e arquivar sob a outra, sem erro — foi como uma revisão de 3.319,7 GWh foi parar numa
    simulação de 109,8 GWh.
    """
    pedido = {k: v for k, v in PEDIDO.items() if k != "restricao_id"}
    pedido["simulacao_id"] = salva["simulacao_id"]
    return pedido


def test_pergunta_e_da_simulacao_e_a_revisao_herda(aprovado: TestClient) -> None:
    primeira = aprovado.post(
        "/simulacoes", json=PEDIDO | {"pergunta": "Um circuito novo se paga?"}
    ).json()
    assert primeira["pergunta"] == "Um circuito novo se paga?"

    revisao = _revisao_de(primeira) | {"pergunta": "outra"}
    segunda = aprovado.post("/simulacoes", json=revisao).json()
    assert segunda["pergunta"] == "Um circuito novo se paga?"
    assert aprovado.get(f"/simulacoes/{segunda['id']}").json()["pergunta"] == (
        "Um circuito novo se paga?"
    )
    assert aprovado.post("/simulacoes", json=PEDIDO).json()["pergunta"] is None


def test_nome_vazio_ou_longo_demais_nao_salva(aprovado: TestClient) -> None:
    assert aprovado.post("/simulacoes", json=PEDIDO | {"nome": ""}).status_code == 422
    assert aprovado.post("/simulacoes", json=PEDIDO | {"nome": "x" * 201}).status_code == 422


def test_fonte_ambas_soma_as_series_e_fica_registrada(aprovado_com_solar: TestClient) -> None:
    """A fonte escolhida tem que aparecer no carimbo **e** ter mexido na série de verdade.

    Eólica: 8 meias horas de 100 MW = 400 MWh. Solar: 4 de 40 MW = 80 MWh. Somadas, 480 MWh.
    Sem as duas pontas juntas o carimbo é afirmação da API que ninguém confere — o motor não lê
    a premissa, e não tem como saber de que fonte é a série que recebeu.
    """

    def cortada(fonte: str) -> float:
        corpo = aprovado_com_solar.post("/simular", json=PEDIDO_SIMULAR | {"fonte": fonte}).json()
        assert corpo["premissas_usadas"]["fonte_geracao"]["valor"] == fonte
        return float(corpo["tecnico"]["energia_cortada_mwh"])

    assert cortada("eolica") == pytest.approx(400.0)
    assert cortada("solar") == pytest.approx(80.0)
    assert cortada("ambas") == pytest.approx(480.0)
    assert cortada("ambas") == pytest.approx(cortada("eolica") + cortada("solar"))

    # A energia cortada é cega a `minutos_cnf`, então sozinha ela não prova que os minutos das
    # duas fontes foram ponderados pela potência, que é a premissa `agregacao_minutos`. A
    # energia **recuperada** prova, porque passa pelo fator de pico:
    #   quatro primeiras meias horas: 140 MW cortados, minutos = (100x30 + 40x10) / 140 = 24,
    #   fator 30/24 = 1,25, e o ganho de 40 MW evita 40 / 1,25 = 32 MW;
    #   quatro últimas: só eólica, 30 minutos, fator 1, e evita os 40 MW inteiros.
    # Total: 4 x 32 x 0,5 + 4 x 40 x 0,5 = **144 MWh**. Com o máximo no lugar da média
    # ponderada daria 160, e com o mínimo, 120.
    ambas = aprovado_com_solar.post("/simular", json=PEDIDO_SIMULAR | {"fonte": "ambas"}).json()
    assert ambas["tecnico"]["energia_recuperada_mwh"] == pytest.approx(144.0)


def test_fonte_no_padrao_nao_rebaixa_a_premissa(aprovado: TestClient) -> None:
    """Fixar a premissa mesmo quando o pedido está no padrão marcaria "o usuário mexeu nisto" em
    toda simulação, e apagaria a validação de um engenheiro no dia em que ela for validada."""
    padrao = aprovado.post("/simular", json=PEDIDO_SIMULAR).json()["premissas_usadas"]
    declarada = PREMISSAS_PADRAO.obter("fonte_geracao")
    assert padrao["fonte_geracao"]["valor"] == declarada.valor
    assert padrao["fonte_geracao"]["status"] == declarada.status.value


def test_fonte_da_revisao_salva_sobrevive(aprovado_com_solar: TestClient) -> None:
    """Era a única entrada do cálculo que não sobrevivia ao salvamento: a revisão gravava um
    número que ninguém conseguia refazer, porque nada dizia de que série ele saiu."""
    salva = aprovado_com_solar.post("/simulacoes", json=PEDIDO | {"fonte": "ambas"}).json()
    inteira = aprovado_com_solar.get(f"/simulacoes/{salva['id']}").json()
    assert inteira["premissas_usadas"]["fonte_geracao"]["valor"] == "ambas"
    assert inteira["resultado"]["tecnico"]["energia_cortada_mwh"] == pytest.approx(480.0)


def test_revisao_que_so_troca_a_fonte_aparece_na_coluna(aprovado_com_solar: TestClient) -> None:
    """O caso que motivou a feature: número diferente e a coluna dizendo que nada mudou.

    A configuração é idêntica nas duas revisões; só a fonte muda, e com ela a série e a energia.
    """
    primeira = aprovado_com_solar.post("/simulacoes", json=PEDIDO).json()
    segunda = aprovado_com_solar.post(
        "/simulacoes",
        json={k: v for k, v in PEDIDO.items() if k != "restricao_id"}
        | {"simulacao_id": primeira["simulacao_id"], "fonte": "ambas"},
    ).json()

    lista = aprovado_com_solar.get("/simulacoes").json()
    revisoes = {r["id"]: r for item in lista for r in item["revisoes"]}
    assert revisoes[segunda["id"]]["o_que_mudou"] == "Fonte de geração: eolica → ambas."
    assert revisoes[primeira["id"]]["o_que_mudou"] == ORIGINAL

    # E o número mudou mesmo, que é o que tornava a frase antiga uma mentira.
    energias = {
        r["id"]: aprovado_com_solar.get(f"/simulacoes/{r['id']}").json()["resultado"]["tecnico"][
            "energia_cortada_mwh"
        ]
        for r in (primeira, segunda)
    }
    assert energias[primeira["id"]] == pytest.approx(400.0)
    assert energias[segunda["id"]] == pytest.approx(480.0)


def test_correcao_minutos_desligada_muda_o_calculo_e_fica_registrada(
    aprovado: TestClient,
) -> None:
    """Com corte de 15 minutos na meia hora, a correção dobra a potência que o circuito vê."""
    with banco.sessao() as s:
        for ponto in s.scalars(select(SerieRestricao)):
            ponto.minutos_cnf = 15
        s.commit()

    ligada = aprovado.post("/simular", json=PEDIDO).json()
    desligada = aprovado.post("/simular", json=PEDIDO | {"correcao_minutos": False}).json()
    assert ligada["premissas_usadas"]["correcao_minutos"]["valor"] is True
    assert desligada["premissas_usadas"]["correcao_minutos"]["valor"] is False
    assert desligada["premissas_usadas"]["correcao_minutos"]["status"] == "proposta"
    assert (
        ligada["tecnico"]["energia_evitada_equipamento_mwh"]
        != desligada["tecnico"]["energia_evitada_equipamento_mwh"]
    )
    assert ligada["metodo_versao"] == desligada["metodo_versao"]

    salva = aprovado.post("/simulacoes", json=PEDIDO | {"correcao_minutos": False}).json()
    inteira = aprovado.get(f"/simulacoes/{salva['id']}").json()
    assert inteira["premissas_usadas"]["correcao_minutos"]["valor"] is False


def test_contrato_tipa_as_respostas_de_simular_e_de_ver_simulacao() -> None:
    from arco_api.main import app

    caminhos = app.openapi()["paths"]

    def resposta(caminho: str, verbo: str) -> dict[str, str]:
        return caminhos[caminho][verbo]["responses"]["200"]["content"]["application/json"]["schema"]

    assert resposta("/simular", "post") == {"$ref": "#/components/schemas/Resultado"}
    assert resposta("/simulacoes/{revisao_id}", "get") == {
        "$ref": "#/components/schemas/RevisaoCompleta"
    }


def test_equipamento_de_fora_da_restricao_nao_simula(aprovado: TestClient) -> None:
    """A linha que recebe o circuito tem de ser uma das validadas da restrição."""
    configuracao = {
        "modalidade": "equipamento",
        "equipamento": {
            "tipo": "adicao_circuito",
            "cod_equipamento": "LINHA-DE-OUTRA-RESTRICAO",
            "ganho_limite_mw": 40.0,
        },
        "financeira": FINANCEIRA,
    }
    recusada = aprovado.post("/simular", json=PEDIDO | {"configuracao": configuracao})
    assert recusada.status_code == 422
    assert "LINHA-DE-OUTRA-RESTRICAO" in recusada.json()["detail"]


def test_subestacao_da_bateria_precisa_ser_terminal_da_restricao(aprovado: TestClient) -> None:
    """A bateria se prende a uma subestação da restrição; qualquer nome não serve."""

    def pedido(subestacao: str) -> dict[str, object]:
        return PEDIDO | {
            "configuracao": {
                "modalidade": "bateria",
                "bateria": {
                    "potencia_mw": 50.0,
                    "capacidade_mwh": 200.0,
                    "subestacao": subestacao,
                },
                "financeira": FINANCEIRA,
            }
        }

    assert aprovado.post("/simular", json=pedido("ACU III")).status_code == 200
    recusada = aprovado.post("/simular", json=pedido("SE QUE NÃO EXISTE"))
    assert recusada.status_code == 422
    assert "SE QUE NÃO EXISTE" in recusada.json()["detail"]


def test_escolhas_ficam_registradas_na_revisao(aprovado: TestClient) -> None:
    """Quem abrir a revisão em janeiro sabe qual linha foi reforçada."""
    salva = aprovado.post("/simulacoes", json=PEDIDO).json()
    inteira = aprovado.get(f"/simulacoes/{salva['id']}").json()
    assert inteira["configuracao"]["equipamento"]["cod_equipamento"] == EQUIPAMENTO


def test_premissas_abrem_a_tela_com_valor_campo_e_status(cliente: TestClient) -> None:
    """A tela abre preenchida sem chumbar número: valor, campo e status vêm do contrato."""
    referencia = cliente.get("/premissas").json()
    assert referencia["cenario"] == "referencia"
    por_campo = {item["campo"]: item["premissa"] for item in referencia["valores_iniciais"]}
    assert por_campo["financeira.taxa_desconto_aa"]["valor"] == 0.08
    assert por_campo["financeira.horizonte_anos"]["valor"] == 30
    assert por_campo["bateria.degradacao_por_ano"]["status"] == "nao_verificada"
    # Nada é `validada`, então nenhum número sai seco: a faixa são os próprios cenários.
    assert por_campo["financeira.taxa_desconto_aa"]["faixa"] == [0.08, 0.12]
    assert all(item["premissa"]["fonte"] for item in referencia["valores_iniciais"])

    def valores(**parametros: str) -> dict[str, object]:
        resposta = cliente.get("/premissas", params=parametros).json()
        return {item["campo"]: item["premissa"]["valor"] for item in resposta["valores_iniciais"]}

    conservador = valores(cenario="conservador")
    assert (
        conservador["financeira.taxa_desconto_aa"],
        conservador["financeira.horizonte_anos"],
    ) == (
        0.12,
        25,
    )
    otimista = valores(cenario="otimista")
    assert (otimista["financeira.taxa_desconto_aa"], otimista["financeira.horizonte_anos"]) == (
        0.08,
        35,
    )

    # Horizonte de linha para uma bateria que morre antes somaria anos de recuperação de um ativo
    # já morto: na modalidade bateria o horizonte é a vida útil dela.
    so_bateria = valores(cenario="referencia", modalidade="bateria")
    assert so_bateria["financeira.horizonte_anos"] == so_bateria["bateria.vida_util_anos"] == 20
    assert valores(cenario="referencia", modalidade="combinada")["financeira.horizonte_anos"] == 30

    # `preco_energia` não é campo de formulário: vazio no pedido, o cálculo cai nela.
    assert any(premissa["id"] == "preco_energia" for premissa in referencia["metodo"])


def test_listagem_agrupa_por_simulacao_com_as_revisoes_dentro(aprovado: TestClient) -> None:
    """Uma linha por simulação. Antes, uma simulação de três revisões ocupava três linhas."""
    primeira = aprovado.post("/simulacoes", json=PEDIDO).json()
    segunda = aprovado.post("/simulacoes", json=_revisao_de(primeira)).json()
    aprovado.post("/simulacoes", json=PEDIDO | {"nome": "Outra simulação"})

    itens = aprovado.get("/simulacoes").json()
    assert [item["nome"] for item in itens] == ["Outra simulação", "Circuito novo"]

    com_historico = itens[1]
    assert [revisao["id"] for revisao in com_historico["revisoes"]] == [
        segunda["id"],
        primeira["id"],
    ]
    assert [revisao["posicao"] for revisao in com_historico["revisoes"]] == [2, 1]
    assert [revisao["atual"] for revisao in com_historico["revisoes"]] == [True, False]


def _declara_a_janela() -> None:
    """A janela mora no snapshot, e o artefato de teste não a traz."""
    with banco.sessao() as s:
        snapshot = s.get(Snapshot, SNAPSHOT)
        assert snapshot is not None
        snapshot.periodo_inicio = datetime(2025, 9, 1)
        snapshot.periodo_fim = datetime(2026, 9, 1)
        s.commit()


def test_item_mostra_restricao_modalidade_janela_e_numeros_sem_abrir(
    aprovado: TestClient,
) -> None:
    """O que o layout mostra no item fechado, sem carregar o resultado inteiro."""
    _declara_a_janela()
    aprovado.post("/simulacoes", json=PEDIDO)
    item = aprovado.get("/simulacoes").json()[0]

    assert item["restricao_texto"].startswith("LT 500 kV")
    assert item["modalidade"] == "equipamento"

    revisao = item["revisoes"][0]
    assert revisao["periodo_inicio"].startswith("2025-09-01")
    assert revisao["periodo_fim"].startswith("2026-09-01")
    assert revisao["energia_recuperada_mwh"] == pytest.approx(160.0)
    assert revisao["vpl_reais"] is not None
    assert "resultado" not in revisao, "o resultado inteiro não viaja na listagem"


def test_o_que_mudou_sai_da_comparacao_com_a_revisao_anterior(aprovado: TestClient) -> None:
    """A coluna não é digitada: ela compara a configuração com a da revisão anterior."""
    primeira = aprovado.post("/simulacoes", json=PEDIDO).json()

    outro_ganho = {
        "modalidade": "equipamento",
        "equipamento": {
            "tipo": "adicao_circuito",
            "cod_equipamento": EQUIPAMENTO,
            "ganho_limite_mw": 25.0,
        },
        "financeira": FINANCEIRA,
    }
    aprovado.post(
        "/simulacoes",
        json=_revisao_de(primeira) | {"configuracao": outro_ganho},
    )
    aprovado.post("/simulacoes", json=_revisao_de(primeira))

    revisoes = aprovado.get("/simulacoes").json()[0]["revisoes"]
    por_posicao = {revisao["posicao"]: revisao["o_que_mudou"] for revisao in revisoes}

    assert por_posicao[1].startswith("Original")
    assert por_posicao[2] == "Ganho de limite: 40 → 25."
    # A terceira volta ao ganho original, e compara com a **segunda**, não com a primeira: sem
    # `revisao_base_id`, a revisão nova nasce da mais nova da simulação.
    assert por_posicao[3] == "Ganho de limite: 25 → 40."


def test_revisao_sem_base_nasce_da_mais_nova(aprovado: TestClient) -> None:
    """Sem `revisao_base_id`, o comportamento de antes da ADR 0014: a tela não escolhe origem,
    e a revisão nasce da que a pessoa está vendo, a mais nova. E sai `por_pessoa`, sem nota."""
    primeira = aprovado.post("/simulacoes", json=PEDIDO).json()
    segunda = aprovado.post("/simulacoes", json=_revisao_de(primeira)).json()
    terceira = aprovado.post("/simulacoes", json=_revisao_de(primeira)).json()

    assert segunda["revisao_anterior_id"] == primeira["id"]
    assert terceira["revisao_anterior_id"] == segunda["id"], "nasceu da mais nova, não da mãe"
    assert {segunda["simulacao_id"], terceira["simulacao_id"]} == {primeira["simulacao_id"]}
    for salva in (primeira, segunda, terceira):
        assert (salva["procedencia"], salva["nota"]) == ("por_pessoa", None)


def test_revisoes_com_a_mesma_base_sao_irmas(aprovado: TestClient) -> None:
    """Duas variações de um lote partem da mesma revisão (ADR 0014). Com "a mais nova", a de
    25 MW ficaria filha da de 60 MW, e "o que mudou" diria 60 → 25 em vez de 40 → 25."""
    primeira = aprovado.post("/simulacoes", json=PEDIDO).json()

    def com_ganho(ganho: float) -> dict[str, object]:
        configuracao = {
            "modalidade": "equipamento",
            "equipamento": {
                "tipo": "adicao_circuito",
                "cod_equipamento": EQUIPAMENTO,
                "ganho_limite_mw": ganho,
            },
            "financeira": FINANCEIRA,
        }
        return _revisao_de(primeira) | {
            "configuracao": configuracao,
            "revisao_base_id": primeira["id"],
        }

    maior = aprovado.post("/simulacoes", json=com_ganho(60.0)).json()
    menor = aprovado.post("/simulacoes", json=com_ganho(25.0)).json()

    assert maior["revisao_anterior_id"] == menor["revisao_anterior_id"] == primeira["id"]
    revisoes = aprovado.get("/simulacoes").json()[0]["revisoes"]
    por_id = {revisao["id"]: revisao for revisao in revisoes}
    assert por_id[maior["id"]]["o_que_mudou"] == "Ganho de limite: 40 → 60."
    assert por_id[menor["id"]]["o_que_mudou"] == "Ganho de limite: 40 → 25."
    # A posição continua sendo a ordem de gravação; a árvore se lê pela origem.
    assert [revisao["posicao"] for revisao in revisoes] == [3, 2, 1]
    assert [revisao["revisao_anterior_id"] for revisao in revisoes] == [
        primeira["id"],
        primeira["id"],
        None,
    ]


def test_base_de_outra_simulacao_ou_inexistente_recusa(aprovado: TestClient) -> None:
    """A origem tem de ser da mesma simulação: de outra, "o que mudou" compararia com a
    configuração de outra simulação, e a árvore atravessaria simulações."""
    uma = aprovado.post("/simulacoes", json=PEDIDO).json()
    outra = aprovado.post("/simulacoes", json=PEDIDO | {"nome": "Outra"}).json()

    de_outra = aprovado.post(
        "/simulacoes", json=_revisao_de(uma) | {"revisao_base_id": outra["id"]}
    )
    inexistente = aprovado.post("/simulacoes", json=_revisao_de(uma) | {"revisao_base_id": 9999})

    assert de_outra.status_code == 422
    assert f"é da simulação {outra['simulacao_id']}" in de_outra.text
    assert inexistente.status_code == 422
    assert "não existe" in inexistente.text
    assert len(aprovado.get(f"/simulacoes/{uma['id']}").json()["revisoes"]) == 1, "nada salvo"


def test_base_ao_criar_simulacao_recusa(aprovado: TestClient) -> None:
    """A primeira revisão de uma simulação não nasce de nenhuma."""
    salva = aprovado.post("/simulacoes", json=PEDIDO).json()

    resposta = aprovado.post("/simulacoes", json=PEDIDO | {"revisao_base_id": salva["id"]})

    assert resposta.status_code == 422
    assert "só vale ao revisar" in resposta.text


@pytest.mark.parametrize("nota", [None, "", "   "])
def test_revisao_por_agente_sem_nota_recusa(aprovado: TestClient, nota: str | None) -> None:
    """O agente escreve sempre o porquê (ADR 0011). Nota em branco é nota ausente."""
    pedido = PEDIDO | {"procedencia": "por_agente"}
    if nota is not None:
        pedido["nota"] = nota

    resposta = aprovado.post("/simulacoes", json=pedido)

    assert resposta.status_code == 422
    assert "exige `nota`" in resposta.text
    assert aprovado.get("/simulacoes").json() == []


def test_nota_longa_demais_recusa(aprovado: TestClient) -> None:
    assert aprovado.post("/simulacoes", json=PEDIDO | {"nota": "x" * 1001}).status_code == 422


def test_procedencia_e_nota_voltam_em_toda_leitura(aprovado: TestClient) -> None:
    """Salvar, abrir, listar e o seletor dizem a mesma coisa sobre como a revisão nasceu."""
    primeira = aprovado.post(
        "/simulacoes", json=PEDIDO | {"nota": "  Circuito de 40 MW, o do estudo.  "}
    ).json()
    do_agente = aprovado.post(
        "/simulacoes",
        json=_revisao_de(primeira)
        | {
            "procedencia": "por_agente",
            "nota": "Rodada 1: a grade de tamanhos mostra onde a curva achata.",
            "revisao_base_id": primeira["id"],
        },
    ).json()

    assert primeira["nota"] == "Circuito de 40 MW, o do estudo.", "nota sai aparada"
    assert (do_agente["procedencia"], do_agente["revisao_anterior_id"]) == (
        "por_agente",
        primeira["id"],
    )

    aberta = aprovado.get(f"/simulacoes/{do_agente['id']}").json()
    assert (aberta["procedencia"], aberta["nota"], aberta["revisao_anterior_id"]) == (
        "por_agente",
        "Rodada 1: a grade de tamanhos mostra onde a curva achata.",
        primeira["id"],
    )
    irmas = {irma["id"]: irma for irma in aberta["revisoes"]}
    listadas = {r["id"]: r for r in aprovado.get("/simulacoes").json()[0]["revisoes"]}
    for vista in (irmas, listadas):
        assert (vista[primeira["id"]]["procedencia"], vista[primeira["id"]]["nota"]) == (
            "por_pessoa",
            "Circuito de 40 MW, o do estudo.",
        )
        assert vista[primeira["id"]]["revisao_anterior_id"] is None
        assert vista[do_agente["id"]]["procedencia"] == "por_agente"
        assert vista[do_agente["id"]]["revisao_anterior_id"] == primeira["id"]


def test_revisao_nao_aceita_restricao_no_pedido(aprovado: TestClient) -> None:
    """A restrição é da simulação. Mandar as duas permitia calcular com a série de uma e
    arquivar sob a outra, sem erro — uma revisão de 3.319,7 GWh numa simulação de 109,8."""
    primeira = aprovado.post("/simulacoes", json=PEDIDO).json()

    com_as_duas = aprovado.post(
        "/simulacoes", json=_revisao_de(primeira) | {"restricao_id": RESTRICAO}
    )
    com_nenhuma = aprovado.post(
        "/simulacoes", json={k: v for k, v in PEDIDO.items() if k != "restricao_id"}
    )

    assert com_as_duas.status_code == 422
    assert com_nenhuma.status_code == 422
    assert "exatamente um" in com_as_duas.text


def test_simulacao_que_nao_existe_responde_404(aprovado: TestClient) -> None:
    pedido = {k: v for k, v in PEDIDO.items() if k != "restricao_id"} | {"simulacao_id": 9999}

    assert aprovado.post("/simulacoes", json=pedido).status_code == 404


def test_revisao_traz_as_irmas_para_o_seletor(aprovado: TestClient) -> None:
    """Quem abre uma revisão por link vê que existem outras, sem carregar a listagem."""
    _declara_a_janela()
    primeira = aprovado.post("/simulacoes", json=PEDIDO).json()
    segunda = aprovado.post("/simulacoes", json=_revisao_de(primeira)).json()

    aberta = aprovado.get(f"/simulacoes/{primeira['id']}").json()
    assert [irma["id"] for irma in aberta["revisoes"]] == [segunda["id"], primeira["id"]]
    assert [irma["atual"] for irma in aberta["revisoes"]] == [True, False]
    assert aberta["periodo_inicio"].startswith("2025-09-01")


def test_bateria_sem_soc_inicial_nao_e_recusada(aprovado: TestClient) -> None:
    """O payload que o front mandou em 2026-09-21 e tomou 422 sem ter escolhido nada.

    `soc_inicial` é opcional; omitido, caía no padrão zero, que é carga proibida sempre que
    `soc_min` for maior que zero. Omitir opcional é a coisa razoável a fazer, e passou a
    funcionar: a bateria começa no piso que a operação permite.
    """
    pedido = {
        "restricao_id": RESTRICAO,
        "fonte": "eolica",
        "configuracao": {
            "modalidade": "bateria",
            "bateria": {
                "subestacao": "ACU III",
                "potencia_mw": 100.0,
                "capacidade_mwh": 400.0,
                "soc_min": 0.2,
                "soc_max": 0.5,
                "eficiencia_ida_volta": 0.85,
                "disponibilidade": 0.959,
                "degradacao_por_ciclo": 0.000076,
                "vida_util_anos": 20,
            },
            "financeira": {
                "cenario": "referencia",
                "taxa_desconto_aa": 0.08,
                "horizonte_anos": 15,
                "capex_reais": 1000.0,
            },
        },
    }

    resposta = aprovado.post("/simular", json=pedido)

    assert resposta.status_code == 200, resposta.text


def test_bateria_com_soc_inicial_fora_da_faixa_continua_recusada(aprovado: TestClient) -> None:
    """Quem escolhe um valor impossível continua sendo avisado, e a mensagem diz os três."""
    pedido = {
        "restricao_id": RESTRICAO,
        "configuracao": {
            "modalidade": "bateria",
            "bateria": {
                "subestacao": "ACU III",
                "potencia_mw": 100.0,
                "capacidade_mwh": 400.0,
                "soc_min": 0.2,
                "soc_inicial": 0.9,
                "soc_max": 0.5,
            },
            "financeira": {
                "cenario": "referencia",
                "taxa_desconto_aa": 0.08,
                "horizonte_anos": 15,
                "capex_reais": 1000.0,
            },
        },
    }

    resposta = aprovado.post("/simular", json=pedido)

    assert resposta.status_code == 422
    assert "soc_inicial=0.9" in resposta.text


def _torna_contingenciada() -> None:
    """A única linha da restrição passa a ser a que se supõe perder."""
    with banco.sessao() as s:
        vinculo = s.scalars(select(VinculoRestricaoEquipamento)).one()
        vinculo.papel = "contingenciado"
        s.commit()


def test_contingenciada_nao_recebe_circuito_novo(aprovado: TestClient) -> None:
    """O motor só modela adição de circuito na monitorada; na contingenciada o VPL seria de uma
    intervenção que não existe. Bloqueia, não avisa (jornada da feature 17)."""
    _torna_contingenciada()

    for rota in ("/simular", "/simulacoes"):
        resposta = aprovado.post(rota, json=PEDIDO)
        assert resposta.status_code == 422, rota
        assert "não recebe circuito novo" in resposta.text
        assert "linha monitorada" in resposta.text


def test_terminal_da_contingenciada_continua_valendo_para_a_bateria(aprovado: TestClient) -> None:
    """A bateria se prende à restrição, não ao equipamento."""
    _torna_contingenciada()
    pedido = PEDIDO | {
        "configuracao": {
            "modalidade": "bateria",
            "bateria": {"subestacao": "ACU III", "potencia_mw": 100.0, "capacidade_mwh": 400.0},
            "financeira": FINANCEIRA,
        }
    }

    assert aprovado.post("/simular", json=pedido).status_code == 200


@pytest.mark.parametrize(
    ("bloco", "campo"),
    [("bateria", "potencia_mw"), ("equipamento", "ganho_limite_mw")],
)
def test_potencia_e_ganho_tem_teto_na_capacidade_da_linha(
    aprovado: TestClient, bloco: str, campo: str
) -> None:
    """A linha da fixture aguenta 3.005 MVA de longa duração. Até 3.005 MW passa; acima, 422
    com o teto e a premissa na mensagem."""
    configuracao = {
        "modalidade": "combinada",
        "bateria": {"subestacao": "ACU III", "potencia_mw": 100.0, "capacidade_mwh": 400.0},
        "equipamento": {
            "tipo": "adicao_circuito",
            "cod_equipamento": EQUIPAMENTO,
            "ganho_limite_mw": 40.0,
        },
        "financeira": FINANCEIRA,
    }

    def com(valor: float) -> dict[str, object]:
        mexida = {k: dict(v) if isinstance(v, dict) else v for k, v in configuracao.items()}
        mexida[bloco][campo] = valor  # type: ignore[index]
        return PEDIDO | {"configuracao": mexida}

    assert aprovado.post("/simular", json=com(3005.0)).status_code == 200
    acima = aprovado.post("/simular", json=com(3005.5))
    assert acima.status_code == 422
    assert "teto de 3.005 MW" in acima.text
    assert "teto_alavanca_capacidade" in acima.text


def _montar(cliente: TestClient, **parametros: str | int | float):  # type: ignore[no-untyped-def]
    return cliente.get(f"/restricoes/{RESTRICAO}/montar", params=parametros)


def test_montar_bateria_devolve_a_configuracao_com_a_conta_do_investimento(
    aprovado: TestClient,
) -> None:
    """50 MW e 200 MWh no cenário de referência: 200.000 kWh x 1.375 R$/kWh = 275 milhões."""
    resposta = _montar(
        aprovado, modalidade="bateria", potencia_mw=50, capacidade_mwh=200, subestacao="ACU III"
    )

    assert resposta.status_code == 200, resposta.text
    montada = resposta.json()
    assert montada["snapshot_id"] == SNAPSHOT
    assert montada["configuracao"]["financeira"]["capex_reais"] == pytest.approx(275_000_000)
    (parcela,) = montada["investimento"]
    assert parcela["custo_unitario"]["id"] == "bateria_capex_kwh"
    assert all(c["status"] for c in montada["campos"] if c["origem"] != "escolha")

    # A configuração montada salva como está: é o botão do cartão.
    salva = aprovado.post(
        "/simulacoes",
        json={
            "restricao_id": RESTRICAO,
            "nome": "Montada",
            "configuracao": montada["configuracao"],
        },
    )
    assert salva.status_code == 200, salva.text


def test_montar_circuito_usa_o_comprimento_e_a_tensao_do_cadastro(aprovado: TestClient) -> None:
    """Linha de 500 kV com 210 km: 210 x 2.471.843 R$/km = 519.087.030 R$."""
    montada = _montar(
        aprovado, modalidade="equipamento", cod_equipamento=EQUIPAMENTO, ganho_limite_mw=40
    ).json()

    assert montada["configuracao"]["financeira"]["capex_reais"] == pytest.approx(519_087_030)
    assert montada["configuracao"]["equipamento"]["cod_equipamento"] == EQUIPAMENTO


def test_montar_recusa_o_que_salvar_recusaria(aprovado: TestClient) -> None:
    sem_subestacao = _montar(aprovado, modalidade="bateria", potencia_mw=50, capacidade_mwh=200)
    assert sem_subestacao.status_code == 422
    assert "subestacao" in sem_subestacao.text

    acima_do_teto = _montar(
        aprovado, modalidade="equipamento", cod_equipamento=EQUIPAMENTO, ganho_limite_mw=4000
    )
    assert acima_do_teto.status_code == 422
    assert "teto" in acima_do_teto.text

    _torna_contingenciada()
    na_contingenciada = _montar(
        aprovado, modalidade="equipamento", cod_equipamento=EQUIPAMENTO, ganho_limite_mw=40
    )
    assert na_contingenciada.status_code == 422
    assert "não recebe circuito novo" in na_contingenciada.text


def test_montar_restricao_que_nao_existe_e_404(aprovado: TestClient) -> None:
    resposta = aprovado.get(
        "/restricoes/nao-existe/montar",
        params={"modalidade": "bateria", "potencia_mw": 1, "capacidade_mwh": 4, "subestacao": "X"},
    )
    assert resposta.status_code == 404


def test_revisao_traz_diagnosticos_e_cruzamentos(aprovado: TestClient) -> None:
    """Bateria de 100 MW e 400 MWh contra os 8 cortes de 100 MW da fixture: sobram 400 - 200 =
    200 MWh, todos às 2h e 3h."""
    pedido = PEDIDO | {
        "configuracao": {
            "modalidade": "bateria",
            "bateria": {"subestacao": "ACU III", "potencia_mw": 100.0, "capacidade_mwh": 400.0},
            "financeira": FINANCEIRA,
        }
    }
    salva = aprovado.post("/simulacoes", json=pedido).json()

    inteira = aprovado.get(f"/simulacoes/{salva['id']}").json()

    diagnosticos = inteira["resultado"]["diagnosticos"]
    assert diagnosticos["corte_residual"]["energia_mwh"] == pytest.approx(
        inteira["resultado"]["tecnico"]["energia_cortada_mwh"]
        - inteira["resultado"]["tecnico"]["energia_recuperada_mwh"]
    )
    assert diagnosticos["saturacao"]["episodios"] == 1
    assert inteira["cruzamentos"] == {"payback_no_horizonte": None, "tir_acima_da_taxa": None}


def test_revisao_de_antes_dos_diagnosticos_os_ganha_na_leitura(aprovado: TestClient) -> None:
    """Revisão gravada antes da 0.9.0 não tem `diagnosticos` no resultado: a leitura calcula,
    com a série do snapshot e da fonte dela, e dá o mesmo que o cálculo teria gravado."""
    salva = aprovado.post("/simulacoes", json=PEDIDO).json()
    gravados = aprovado.get(f"/simulacoes/{salva['id']}").json()["resultado"]["diagnosticos"]
    with banco.sessao() as s:
        revisao = s.get(SimulacaoRevisao, salva["id"])
        assert revisao is not None
        revisao.resultado = {k: v for k, v in revisao.resultado.items() if k != "diagnosticos"}
        s.commit()

    lidos = aprovado.get(f"/simulacoes/{salva['id']}").json()["resultado"]["diagnosticos"]

    assert lidos == gravados
