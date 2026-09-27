"""Relatório da simulação pela API (feature 17, task 17.4), com o modelo substituído.

Roda em SQLite sem configuração e em Postgres com `ARCO_TEST_DATABASE_URL`, como a suíte de
carga e rotas, de onde vêm o banco, os artefatos e o pedido de simulação.

O `TestClient` roda a tarefa de fundo antes de devolver a resposta do `POST`: a resposta diz
`gerando`, que é o que o cliente recebe na hora, e o `GET` seguinte já vê o estado final.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from arco_api import banco, modelos
from arco_api import relatorio as api_relatorio
from arco_ia import IndisponivelSemChave
from arco_ia import relatorio as ia_relatorio
from arco_ia.chamada import Registro, Resposta
from arco_ia.relatorio import Prosa

_ESPEC = importlib.util.spec_from_file_location(
    "carga_e_rotas", Path(__file__).with_name("test_carga_e_rotas.py")
)
assert _ESPEC is not None and _ESPEC.loader is not None
carga_e_rotas = importlib.util.module_from_spec(_ESPEC)
_ESPEC.loader.exec_module(carga_e_rotas)

# As fixtures da suíte de carga e rotas, reusadas por nome.
banco_vazio = carga_e_rotas.banco_vazio
artefatos = carga_e_rotas.artefatos
cliente = carga_e_rotas.cliente
aprovado = carga_e_rotas.aprovado
PEDIDO: dict[str, Any] = carga_e_rotas.PEDIDO
_revisao_de = carga_e_rotas._revisao_de

REGISTRO = Registro(
    papel="analista",
    modelo="modelo-de-teste",
    versao_prompt="9",
    tokens_entrada=1,
    tokens_saida=1,
    latencia_s=0.0,
    tentativas=1,
    validacao="aceita",
)

VALIDA = Prosa(
    leitura_geral="A simulação cobre as rev 1 e 2 de adição de circuito.",
    o_que_variou=["O ganho de limite variou entre as rev 1 e 2."],
    sensibilidade="O VPL mudou com o ganho de limite entre as revisões cobertas.",
    fora_do_metodo="O resultado é contrafactual. Associação não é causalidade.",
    perguntas_que_ficaram=["Como o VPL responde a outra taxa de desconto?"],
)
INVALIDA = VALIDA.model_copy(
    update={"sensibilidade": "Cada MW somou R$ 987.654 de VPL, e recomenda-se a rev 2."}
)


@pytest.fixture
def analista(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O analista substituído: devolve a prosa que o teste puser em `prosa`, e guarda a entrada."""
    estado: dict[str, Any] = {"prosa": VALIDA, "entradas": []}

    def escrever(parte: Any, cliente: Any = None) -> Resposta[Prosa]:
        estado["entradas"].append(parte)
        if isinstance(estado["prosa"], Exception):
            raise estado["prosa"]
        return Resposta(saida=estado["prosa"], registro=REGISTRO)

    monkeypatch.setattr(ia_relatorio, "escrever_prosa", escrever)
    return estado


def _duas_revisoes(cliente: TestClient) -> dict[str, Any]:
    primeira = cliente.post("/simulacoes", json=PEDIDO).json()
    segunda = _revisao_de(primeira)
    segunda["configuracao"] = {
        **PEDIDO["configuracao"],
        "equipamento": {**PEDIDO["configuracao"]["equipamento"], "ganho_limite_mw": 80.0},
    }
    cliente.post("/simulacoes", json=segunda)
    return primeira


def test_post_responde_202_em_gerando_e_o_get_ve_pronto(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    resposta = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios")
    assert resposta.status_code == 202
    criado = resposta.json()
    assert (criado["simulacao_id"], criado["estado"]) == (simulacao_id, "gerando")

    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()
    assert lido["estado"] == "pronto"
    assert lido["gerado_em"] is not None
    assert (lido["modelo"], lido["versao_prompt"]) == ("modelo-de-teste", "9")
    assert lido["nome"] == PEDIDO["nome"]
    assert lido["revisoes_cobertas"] == [1, 2]
    assert lido["revisoes_novas"] == []
    assert lido["prosa"] == VALIDA.model_dump()
    assert lido["verificacao"]["resultado"] == "passou"
    assert lido["verificacao"]["numeros_na_prosa"] == lido["verificacao"]["encontrados"]
    assert lido["erro"] is None

    cabecalho = lido["cabecalho"]
    assert cabecalho["restricao_id"] == carga_e_rotas.RESTRICAO
    assert cabecalho["fonte"] == "eolica"
    assert cabecalho["energia_cortada_mwh"] == pytest.approx(400.0)
    assert [f["fonte"] for f in cabecalho["fatia_por_fonte"]] == ["eolica"]
    assert cabecalho["ocorrencias"]["total"] == 1
    assert len(cabecalho["ocorrencias"]["maiores"]) == 1
    assert cabecalho["equipamentos"][0]["cod_equipamento"] == carga_e_rotas.EQUIPAMENTO

    assert [p["posicao"] for p in lido["trilha"]] == [1, 2]
    assert lido["trilha"][0]["origem_do_texto"] == "resumo_da_configuracao"
    assert lido["trilha"][0]["texto"].startswith("Circuito novo em CEJGII5ACT-1RN")
    assert [linha["posicao"] for linha in lido["por_revisao"]] == [1, 2]
    assert lido["por_revisao"][1]["alavanca"] == "CEJGII5ACT-1RN · ganho 80 MW"
    assert lido["por_revisao"][0]["url"] == f"/simulacoes/{lido['trilha'][0]['revisao_id']}"

    derivados = lido["derivados"]
    assert [d["revisao_id"] for d in derivados["diferencas"]] == [lido["trilha"][1]["revisao_id"]]
    assert derivados["diferencas"][0]["o_que_mudou"].startswith("Ganho de limite: 40 → 80")
    (sensibilidade,) = derivados["sensibilidades"]
    assert (sensibilidade["tipo"], sensibilidade["campo"]) == (
        "numerica",
        "equipamento.ganho_limite_mw",
    )
    assert sensibilidade["rotulo"] == "Ganho de limite"
    assert {c["campo"] for c in derivados["variou"]} == {"equipamento.ganho_limite_mw"}
    assert len(lido["nao_afirma"]) == 8
    assert cabecalho["snapshot_id"] == carga_e_rotas.SNAPSHOT


def test_analista_recebe_a_parte_calculada_a_simulacao_e_o_texto_fixo(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    aprovado.post(f"/simulacoes/{simulacao_id}/relatorios")
    (entrada,) = analista["entradas"]
    assert set(entrada) == {
        "simulacao",
        "cabecalho",
        "trilha",
        "derivados",
        "por_revisao",
        "nao_afirma",
    }
    assert entrada["simulacao"]["nome"] == PEDIDO["nome"]


def test_prosa_invalida_barra_com_as_falhas_e_sem_prosa(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    analista["prosa"] = INVALIDA
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()
    assert lido["estado"] == "barrado"
    assert lido["prosa"] is None
    assert lido["derivados"] is not None
    falhas = {(f["secao"], f["motivo"]) for f in lido["verificacao"]["falhas"]}
    assert falhas == {("sensibilidade", "sem_origem"), ("sensibilidade", "forma_proibida")}
    with banco.sessao() as s:
        guardada = s.get(modelos.Relatorio, criado["id"])
        assert guardada is not None
        assert guardada.prosa_barrada == INVALIDA.model_dump(mode="json")


def test_sem_chave_o_relatorio_falha_dizendo_por_que(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    analista["prosa"] = IndisponivelSemChave("GEMINI_API_KEY não está no ambiente")
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()
    assert lido["estado"] == "falhou"
    assert "GEMINI_API_KEY" in lido["erro"]
    assert lido["prosa"] is None
    assert lido["derivados"] is not None, "a parte calculada é código e sai mesmo sem modelo"
    # A falha libera a simulação: pedir de novo é aceito.
    analista["prosa"] = VALIDA
    assert aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").status_code == 202


def test_falha_no_verificador_tambem_vira_falhou(
    aprovado: TestClient, analista: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tarefa de fundo não tem a quem levantar: qualquer falha vira `falhou`, e a simulação
    fica livre para outro pedido."""

    def quebra(*_: Any) -> None:
        raise RuntimeError("verificador quebrou")

    monkeypatch.setattr(ia_relatorio, "verificar", quebra)
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()
    assert lido["estado"] == "falhou"
    assert lido["erro"] == "verificador: RuntimeError: verificador quebrou"
    assert lido["derivados"] is not None


def test_tarefa_que_termina_depois_de_declarada_perdida_nao_sobrescreve(
    aprovado: TestClient, analista: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    gerar = api_relatorio.gerar
    monkeypatch.setattr(api_relatorio, "gerar", lambda _id: None)
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    preso = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    with banco.sessao() as s:
        linha = s.get(modelos.Relatorio, preso["id"])
        assert linha is not None
        linha.estado, linha.erro = "falhou", "perdido"
        s.commit()
    gerar(preso["id"])  # a tarefa pendurada termina agora
    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{preso['id']}").json()
    assert (lido["estado"], lido["erro"], lido["prosa"]) == ("falhou", "perdido", None)


def test_segundo_post_durante_gerando_responde_409(
    aprovado: TestClient, analista: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_relatorio, "gerar", lambda _id: None)
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    assert aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").status_code == 202
    assert aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").status_code == 409


def test_gerando_perdido_vira_falhou_e_libera_o_pedido(
    aprovado: TestClient, analista: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_relatorio, "gerar", lambda _id: None)
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    preso = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    with banco.sessao() as s:
        linha = s.get(modelos.Relatorio, preso["id"])
        assert linha is not None
        linha.criado_em = datetime.now(UTC) - timedelta(hours=1)
        s.commit()
    assert aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").status_code == 202
    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{preso['id']}").json()
    assert lido["estado"] == "falhou"


def test_relatorio_em_gerando_se_le_sem_parte_calculada(
    aprovado: TestClient, analista: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_relatorio, "gerar", lambda _id: None)
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()
    assert lido["estado"] == "gerando"
    assert (lido["gerado_em"], lido["cabecalho"], lido["derivados"], lido["prosa"]) == (
        None,
        None,
        None,
        None,
    )
    assert lido["verificacao"]["resultado"] is None
    assert lido["revisoes_cobertas"] == [1, 2]


def test_revisao_criada_depois_aparece_como_nova(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    primeira = _duas_revisoes(aprovado)
    simulacao_id = primeira["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    terceira = aprovado.post("/simulacoes", json=_revisao_de(primeira)).json()

    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()
    assert lido["revisoes_cobertas"] == [1, 2]
    assert [(n["revisao_id"], n["posicao"]) for n in lido["revisoes_novas"]] == [
        (terceira["id"], 3)
    ]
    (na_lista,) = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios").json()
    assert na_lista["revisoes_novas"][0]["posicao"] == 3


def test_simulacao_com_uma_revisao_gera_derivados_vazios(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    simulacao_id = aprovado.post("/simulacoes", json=PEDIDO).json()["simulacao_id"]
    analista["prosa"] = VALIDA.model_copy(
        update={
            "leitura_geral": "A simulação tem uma revisão só, e não há comparação.",
            "o_que_variou": [],
            "sensibilidade": "Sem par de revisões, não há sensibilidade observada.",
        }
    )
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()
    assert lido["estado"] == "pronto"
    derivados = lido["derivados"]
    assert derivados["diferencas"] == derivados["sensibilidades"] == derivados["variou"] == []
    assert all(lista == [] for lista in derivados["ordenacoes"].values())
    assert lido["revisoes_cobertas"] == [1]


def test_pedir_de_novo_cria_outro_e_a_lista_vem_do_mais_novo(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    primeiro = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    segundo = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    assert primeiro["id"] != segundo["id"]
    lista = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios").json()
    assert [r["id"] for r in lista] == [segundo["id"], primeiro["id"]]
    assert all(r["estado"] == "pronto" for r in lista)


def test_simulacao_ou_relatorio_que_nao_existe_responde_404(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    assert aprovado.post("/simulacoes/999/relatorios").status_code == 404
    assert aprovado.get("/simulacoes/999/relatorios").status_code == 404
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    assert aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/999").status_code == 404


def test_relatorio_de_outra_simulacao_nao_se_le_por_esta(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    uma = _duas_revisoes(aprovado)["simulacao_id"]
    outra = aprovado.post("/simulacoes", json=PEDIDO).json()["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{uma}/relatorios").json()
    assert aprovado.get(f"/simulacoes/{outra}/relatorios/{criado['id']}").status_code == 404


def test_o_banco_guarda_as_revisoes_cobertas_por_id(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    simulacao_id = _duas_revisoes(aprovado)["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()
    with banco.sessao() as s:
        ids = s.scalars(
            select(modelos.SimulacaoRevisao.id)
            .where(modelos.SimulacaoRevisao.simulacao_id == simulacao_id)
            .order_by(modelos.SimulacaoRevisao.id)
        ).all()
        guardado = s.get(modelos.Relatorio, criado["id"])
        assert guardado is not None
        assert guardado.revisoes_cobertas == list(ids)


@pytest.mark.parametrize(
    "caso",
    sorted((Path(__file__).parents[2] / "ia" / "tests" / "avaliacao" / "casos").glob("*.json")),
    ids=lambda caminho: caminho.stem,
)
def test_casos_da_avaliacao_tem_o_formato_da_parte_calculada(caso: Path) -> None:
    """Os casos de ouro do analista são gerados sem a API, porque `ia` não a importa. Este teste
    é o que impede o formato deles de se afastar do que a API entrega ao analista."""
    import json

    entrada = json.loads(caso.read_text(encoding="utf-8"))
    assert set(entrada) == {"simulacao", "nao_afirma", *api_relatorio.ParteCalculada.model_fields}
    api_relatorio.ParteCalculada.model_validate(entrada)
    assert entrada["nao_afirma"] == [i.model_dump() for i in api_relatorio.NAO_AFIRMA], (
        "a avaliação tem de testar o texto fixo que vai para produção"
    )


def test_texto_fixo_nao_tem_forma_proibida() -> None:
    """O analista lê o texto fixo e reaproveita as palavras dele: se ele disser "vencedora", a
    prosa diz também, e o verificador barra."""
    for item in api_relatorio.NAO_AFIRMA:
        assert not ia_relatorio.FORMAS_PROIBIDAS.search(f"{item.titulo}. {item.texto}"), item


def test_irmas_comparam_com_a_origem_e_a_trilha_traz_a_nota(
    aprovado: TestClient, analista: dict[str, Any]
) -> None:
    """Da rev 1 (ganho 40) nascem duas irmãs, ganho 80 e ganho 20, esta salva por agente. Pela
    ordem de gravação a de 20 seria comparada com a de 80; pela origem, as duas comparam com a
    de 40, e as duas sensibilidades são numéricas no ganho."""
    primeira = aprovado.post("/simulacoes", json=PEDIDO | {"nota": "O circuito do estudo."}).json()

    def irma(ganho: float, **extra: Any) -> dict[str, Any]:
        pedido = _revisao_de(primeira) | {"revisao_base_id": primeira["id"]} | extra
        pedido["configuracao"] = {
            **PEDIDO["configuracao"],
            "equipamento": {**PEDIDO["configuracao"]["equipamento"], "ganho_limite_mw": ganho},
        }
        return aprovado.post("/simulacoes", json=pedido).json()

    irma(80.0)
    do_agente = irma(20.0, procedencia="por_agente", nota="Rodada 1: e se o ganho for menor?")
    simulacao_id = primeira["simulacao_id"]
    criado = aprovado.post(f"/simulacoes/{simulacao_id}/relatorios").json()

    lido = aprovado.get(f"/simulacoes/{simulacao_id}/relatorios/{criado['id']}").json()

    sensibilidades = lido["derivados"]["sensibilidades"]
    assert {s["de_revisao_id"] for s in sensibilidades} == {primeira["id"]}
    assert [s["tipo"] for s in sensibilidades] == ["numerica", "numerica"]
    assert {d["anterior_revisao_id"] for d in lido["derivados"]["diferencas"]} == {primeira["id"]}
    trilha = {p["revisao_id"]: p for p in lido["trilha"]}
    assert (trilha[primeira["id"]]["origem_do_texto"], trilha[primeira["id"]]["texto"]) == (
        "nota_da_pessoa",
        "O circuito do estudo.",
    )
    passo = trilha[do_agente["id"]]
    assert (passo["procedencia"], passo["origem_do_texto"]) == ("por_agente", "nota_do_agente")
    assert passo["texto"] == "Rodada 1: e se o ganho for menor?"
