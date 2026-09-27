"""Casamento contra o cadastro e o preparo de ponta a ponta.

O casamento é testado com um cadastro sintético, então roda em qualquer máquina. O preparo
inteiro precisa de um snapshot baixado, e é pulado quando não há: `make snapshot` traz um.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from arco_dados.preparar import (
    AMBIGUO,
    CASADO,
    PROVAVEL,
    SEM_CANDIDATO,
    Linha,
    _canonicos,
    _ler_texto,
    casar,
    preparar,
    restricao_id,
)
from arco_dados.texto import FLUXO, SISTEMICA, TRANSFORMACAO, extrair

SNAPSHOTS = Path(__file__).resolve().parents[2] / "dados" / "snapshots"

ACU_JAGUARUANA = Linha(
    cod_equipamento="CEJGII5ACT-1RN",
    tensao_kv=500,
    de="JAGUARUANA II",
    para="ACU III",
    codigo_circuito="V7",
)
IRECE_CHAPEU = Linha(
    cod_equipamento="BAIRC-2MCH-1",
    tensao_kv=230,
    de="IRECE",
    para="MORRO CHAPEU II",
    codigo_circuito="S5",
)
OUTRA = Linha(
    cod_equipamento="XXYYY-5ZZZ-1",
    tensao_kv=500,
    de="OUTRA",
    para="COISA",
    codigo_circuito="V7",
)


def citado(texto: str):
    (equipamento,) = extrair(texto)
    return equipamento


def test_casa_com_o_par_invertido_e_o_acento_do_texto() -> None:
    """O texto escreve AÇU III / JAGUARUANA II; o cadastro guarda JAGUARUANA II / ACU III."""
    alvo = citado("LT 500 KV AÇU III / JAGUARUANA II – C1(V7)")
    situacao, codigos = casar(alvo, [ACU_JAGUARUANA, OUTRA])
    assert situacao == CASADO
    assert codigos == ["CEJGII5ACT-1RN"]


def test_casa_provavel_quando_o_cadastro_abrevia() -> None:
    """ "MORRO DO CHAPÉU II" no texto, "MORRO CHAPEU II" no cadastro: precisa de olho humano."""
    alvo = citado("LT 230 KV IRECÊ / MORRO DO CHAPÉU II – C1(S5)")
    situacao, codigos = casar(alvo, [IRECE_CHAPEU])
    assert situacao in (CASADO, PROVAVEL)
    assert codigos == ["BAIRC-2MCH-1"]


def test_sem_candidato_nao_inventa() -> None:
    alvo = citado("LT 500 KV INEXISTENTE I / INEXISTENTE II – C1(Z9)")
    assert casar(alvo, [ACU_JAGUARUANA, IRECE_CHAPEU]) == (SEM_CANDIDATO, [])


def test_ambiguo_devolve_todos_os_candidatos() -> None:
    gemea = Linha(
        cod_equipamento="GEMEA-5AAA-1",
        tensao_kv=500,
        de="ACU III",
        para="JAGUARUANA II",
        codigo_circuito="V7",
    )
    alvo = citado("LT 500 KV AÇU III / JAGUARUANA II – C1(V7)")
    situacao, codigos = casar(alvo, [ACU_JAGUARUANA, gemea])
    assert situacao == AMBIGUO
    assert codigos == ["CEJGII5ACT-1RN", "GEMEA-5AAA-1"]


def test_identificador_da_restricao_depende_do_texto_e_nao_do_snapshot() -> None:
    assert restricao_id("abc") == restricao_id("abc")
    assert restricao_id("abc") != restricao_id("abd")
    assert len(restricao_id("abc")) == 12


def _snapshot_disponivel() -> Path | None:
    if not SNAPSHOTS.is_dir():
        return None
    pastas = sorted(p for p in SNAPSHOTS.iterdir() if p.is_dir())
    return pastas[-1] if pastas else None


@pytest.mark.skipif(_snapshot_disponivel() is None, reason="sem snapshot local; rode make snapshot")
def test_preparo_de_ponta_a_ponta(tmp_path: Path) -> None:
    """Roda o preparo sobre um snapshot de verdade e confere o que o artefato tem.

    Não fixa contagens, que mudam a cada snapshot: confere as propriedades que não podem
    mudar — todo artefato existe, toda linha carrega snapshot_id, nada é casado no escuro.
    """
    snapshot = _snapshot_disponivel()
    assert snapshot is not None
    resumo = preparar(snapshot, tmp_path)

    esperados = {
        "restricoes.parquet",
        "serie.parquet",
        "equipamentos.parquet",
        "subestacoes.parquet",
        "propostas_vinculo.parquet",
    }
    assert {arquivo.name for arquivo in tmp_path.iterdir()} == esperados
    assert resumo.restricoes > 0
    assert resumo.intervalos > 0
    assert resumo.propostas == resumo.casadas + resumo.sem_casamento

    import duckdb

    con = duckdb.connect()
    for arquivo in esperados:
        (sem_snapshot,) = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{tmp_path / arquivo}') WHERE snapshot_id IS NULL"
        ).fetchone() or (0,)
        assert sem_snapshot == 0, f"{arquivo} tem linha sem snapshot_id"

    (nao_proposto,) = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{tmp_path / 'propostas_vinculo.parquet'}')"
        " WHERE status <> 'proposto' OR origem <> 'parser'"
    ).fetchone() or (0,)
    assert nao_proposto == 0, "o parser nunca valida vínculo: quem aprova é gente"

    # Escopo: o artefato só carrega inequação que vigia linha de transmissão.
    assert resumo.fora_do_escopo, "nenhum texto fora de escopo é suspeito: o ONS publica vários"
    assert set(resumo.fora_do_escopo) <= {TRANSFORMACAO, FLUXO, SISTEMICA}
    (com_nome,) = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{tmp_path / 'restricoes.parquet'}')"
        " WHERE texto ILIKE '%TRANSFORMA%' AND texto NOT ILIKE '%CARREGAMENTO DA LT%'"
    ).fetchone() or (0,)
    assert com_nome == 0, "restrição de transformação foi ingerida"
    assert resumo.indeterminados == [], "o classificador não leu " + "; ".join(
        resumo.indeterminados
    )


MESMO_GARGALO = [
    "Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV JAGUARUANA II /"
    " PACATUBA – C1(L1) - IO-ON.NE.5NE",
    "Limitação da Transmissão na LT 500 kV Jaguaruana II / Pacatuba – C1(L1),"
    " conforme IO-ON.NE.5NE.",
]


def _mapa(textos: list[str]) -> dict[str, str]:
    return _canonicos({texto: _ler_texto(texto) for texto in textos})


def test_textos_com_tudo_igual_viram_uma_restricao_so() -> None:
    """O ONS escreve o mesmo gargalo de mais de um jeito no mesmo snapshot.

    Em 2026-09-21, `LT 500 kV Jaguaruana II / Pacatuba · C1` estava em cinco textos, e o produto
    mostrava como cinco gargalos o que fisicamente é um.
    """
    mapa = _mapa(MESMO_GARGALO)
    assert len(set(mapa.values())) == 1, "os dois passam a representar a mesma restrição"


def test_instrucao_de_operacao_diferente_nao_junta() -> None:
    """Dois códigos de Instrução podem ser regimes operativos distintos.

    Fundir inequações diferentes soma a energia das duas, que é pior que deixá-las separadas.
    """
    outro_io = MESMO_GARGALO[0].replace("IO-ON.NE.5NE", "IO-PM.NE.5NE")
    mapa = _mapa([MESMO_GARGALO[0], outro_io])
    assert len(set(mapa.values())) == 2


def test_contingencia_diferente_nao_junta() -> None:
    mapa = _mapa(
        [
            "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV BOM NOME / MILAGRES"
            " – C1(L1) PREVENINDO A PERDA DA LT 230 KV ABAIARA / MILAGRES – C1(L2) - IO-ON.NE.2NO",
            "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV BOM NOME / MILAGRES"
            " – C1(L1) PREVENINDO A PERDA DA LT 230 KV MAURITI II / MILAGRES – C1(L3)"
            " - IO-ON.NE.2NO",
        ]
    )
    assert len(set(mapa.values())) == 2


def test_texto_sem_nome_extraido_representa_a_si_mesmo() -> None:
    """Sem nome não há com que comparar, e juntar por semelhança de texto seria palpite."""
    textos = ["Controle de inequação: TEXTO QUE O REGEX NAO LE", "Outro que ele tambem nao le"]
    mapa = _mapa(textos)
    assert mapa == {t: t for t in textos}


def test_representante_nao_depende_da_ordem_de_leitura() -> None:
    """O identificador do grupo não pode mudar conforme a ordem em que o DuckDB devolve."""
    assert _mapa(MESMO_GARGALO) == _mapa(list(reversed(MESMO_GARGALO)))


@pytest.mark.skipif(_snapshot_disponivel() is None, reason="sem snapshot local; rode make snapshot")
def test_extrator_injetado_so_entra_onde_a_regra_nao_leu(tmp_path: Path) -> None:
    """O modelo ataca o resíduo, e só o resíduo.

    O que autoriza o vínculo é a conferência contra o cadastro, não quem leu o texto — por isso
    a proposta de modelo nasce com a mesma `situacao` e sujeita às mesmas recusas.

    **Desde a task 14.1 o resíduo é vazio neste snapshot**, e por isso o extrator não é chamado
    nenhuma vez: a regra passou a ler citação sem código de circuito e citação pelo código
    operativo, que eram os dois padrões que sobravam. O teste guarda as duas coisas — que o
    extrator só vê o que a regra não leu, e que hoje isso é nada. Se um snapshot novo trouxer
    texto de forma desconhecida, `vistos` deixa de ser vazio e a segunda asserção cai, que é o
    aviso de que a regra precisa crescer.

    A conferência da proposta de modelo contra o cadastro é exercitada em `ia/tests/`, que não
    depende de haver resíduo no dado real.
    """
    snapshot = _snapshot_disponivel()
    assert snapshot is not None

    vistos: list[str] = []

    def extrator(texto: str) -> list:
        vistos.append(texto)
        return []

    preparar(snapshot, tmp_path, extrator=extrator)

    assert all(not extrair(texto) for texto in vistos), (
        "o extrator não é chamado onde a regra já leu: seria pagar por resposta que já se tem"
    )
    assert vistos == [], (
        "a regra deixou de ler algum texto do escopo; veja se `extrair` precisa de outra forma"
    )

    con = duckdb.connect()
    propostas = tmp_path / "propostas_vinculo.parquet"
    por_origem = dict(
        con.execute(f"SELECT origem, count(*) FROM '{propostas}' GROUP BY origem").fetchall()
    )
    assert set(por_origem) == {"parser"}, "sem resíduo, toda proposta é da regra"

    situacoes = {
        s
        for (s,) in con.execute(
            f"SELECT DISTINCT situacao FROM '{propostas}' WHERE origem = 'modelo'"
        ).fetchall()
    }
    assert situacoes <= {CASADO, PROVAVEL, AMBIGUO, SEM_CANDIDATO}, (
        "a proposta de modelo é classificada pela mesma conferência"
    )
