"""Citação que o regex não lia: sem código de circuito, e pelo código operativo.

Task 14.1 mais a pendência do `casar()`. Os dois padrões aparecem no snapshot de 2026-09-15 e
valiam 139,5 GWh de linha de transmissão que o produto perdia — classificadas no escopo, mas sem
equipamento, sem nome e sem vínculo.
"""

from __future__ import annotations

import duckdb
import pytest

from arco_dados.preparar import CASADO, PROVAVEL, Linha, casar, ler_cadastro
from arco_dados.texto import CONTINGENCIADO, MONITORADO, extrair, nome_curto

ITABIRA = (
    "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV ITABIRA 4 / ITABIRA 5 PARA "
    "CONTINGÊNCIA DUPLA DAS LT 500 KV ITABIRA 5 / VESPASIANO 2 E LT 500 KV ITABIRA 5 / "
    "NEVES 1 - IO-ON.SE.5MG"
)
JAGUARA = (
    "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 345 KV JAGUARA / LUIZ CARLOS "
    "BARRETO PARA CONTINGÊNCIA DA LT 500 KV JAGUARA / ESTREITO - IO-ON.SE.3RG"
)
JAGUARA_COLADO = (
    "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 345KV JAGUARA/LUIZ CARLOS BARRETO "
    "PARA CONTINGÊNCIA DA LT 500KV JAGUARA/ESTREITO, CONFORME IO-ON.SE.3RG."
)
AQUIRAZ = (
    "Controle de carregamento da LT 04F1 Aquiraz II / Fortaleza, prevenindo a perda dupla das "
    "LTs 04F2 e 04F3 Aquiraz II / Fortaleza."
)


def monitorado(texto: str):  # type: ignore[no-untyped-def]
    lidos = [c for c in extrair(texto) if c.papel == MONITORADO]
    assert lidos, f"nenhum monitorado lido em {texto[:60]}"
    return lidos[0]


@pytest.mark.parametrize(
    ("texto", "gwh", "de", "para", "kv"),
    [
        (ITABIRA, 61.69, "ITABIRA 4", "ITABIRA 5", 230),
        (JAGUARA, 13.48, "JAGUARA", "LUIZ CARLOS BARRETO", 345),
        (JAGUARA_COLADO, 9.76, "JAGUARA", "LUIZ CARLOS BARRETO", 345),
    ],
)
def test_citacao_sem_codigo_de_circuito(
    texto: str, gwh: float, de: str, para: str, kv: int
) -> None:
    """`_PAR` exigia o sufixo `– C1(XX)`, e sem ele o texto saía sem equipamento nenhum."""
    lido = monitorado(texto)

    assert (lido.tensao_kv, lido.de, lido.para) == (kv, de, para)
    assert lido.codigo_circuito is None, "o texto não nomeia circuito; não se inventa"
    assert lido.ordem_circuito is None


def test_citacao_pelo_codigo_operativo() -> None:
    """`LT 04F1 ...`: `04` é a classe de tensão e `F1` é o circuito.

    Conferido no cadastro de 2026-09-15: `04F1` **não** é `cod_equipamento` — a linha é
    `CEAQR-2FTZ-1`. A tensão fica vazia de propósito: mapear a classe `04` para 230 kV seria
    premissa sem fonte, e quem sabe a tensão é o cadastro.
    """
    lido = monitorado(AQUIRAZ)

    assert (lido.de, lido.para) == ("AQUIRAZ II", "FORTALEZA")
    assert lido.codigo_circuito == "F1"
    assert lido.tensao_kv is None


def test_o_nome_omite_o_que_o_texto_nao_diz() -> None:
    """Campo ausente some do nome; a ordem dos que sobram não muda, e nada se inventa."""
    assert nome_curto(extrair(ITABIRA)) == "LT 230 kV Itabira 4 / Itabira 5"
    assert nome_curto(extrair(AQUIRAZ)) == "LT Aquiraz II / Fortaleza"


def test_papel_gruda_depois_da_marca_de_contingencia() -> None:
    """`DAS LT B E LT C`: a marca aparece só antes de B, e C ficava como monitorada.

    Uma linha que se supõe perder entrando como candidata a receber circuito novo é o mesmo
    defeito que a feature 14 achou do outro lado, no texto de São João do Piauí.
    """
    papeis = [(c.de, c.para, c.papel) for c in extrair(ITABIRA)]

    assert papeis == [
        ("ITABIRA 4", "ITABIRA 5", MONITORADO),
        ("ITABIRA 5", "VESPASIANO 2", CONTINGENCIADO),
        ("ITABIRA 5", "NEVES 1", CONTINGENCIADO),
    ]


def test_quando_da_perda_tambem_abre_contingencia() -> None:
    """A terceira forma de abrir a lista, que `CONTING|PREVENINDO A PERDA` não pegava."""
    texto = (
        "Controle de carregamento da LT 230 kV Fortaleza / Aquiraz (04F1) quando da perda "
        "dupla das LTs 230 kV Fortaleza / Aquiraz II (04F2 e 04F3)"
    )

    assert [c.papel for c in extrair(texto)] == [MONITORADO, CONTINGENCIADO]


CADASTRO = [
    Linha("MGIBAQ2ITB51", 230, "ITABIRA 4", "ITABIRA 5", "1"),
    Linha("MGITAB2ITB51", 230, "ITABIRA 2", "ITABIRA 5", "1"),
    Linha("MGJGUS3USLB1SP", 345, "JAGUARA-345", "L.C.BARRETO", "1"),
    Linha("CEAQR-2FTZ-1", 230, "AQUIRAZ II", "FORTALEZA", "F1"),
    Linha("CEAQR-2FTZ-2", 230, "AQUIRAZ II", "FORTALEZA", "F2"),
]


def test_casar_sem_circuito_usa_tensao_mais_par() -> None:
    """Chave que o texto não dá não filtra. Antes, circuito vazio zerava os candidatos."""
    situacao, codigos = casar(monitorado(ITABIRA), CADASTRO)

    assert (situacao, codigos) == (CASADO, ["MGIBAQ2ITB51"])


def test_casar_sem_tensao_usa_circuito_mais_par() -> None:
    """O espelho: `LT 04F1` não diz a tensão, e o circuito mais o par bastam."""
    situacao, codigos = casar(monitorado(AQUIRAZ), CADASTRO)

    assert (situacao, codigos) == (CASADO, ["CEAQR-2FTZ-1"])


def test_o_hifen_do_cadastro_quebra_em_token() -> None:
    """`JAGUARA-345` é a mesma subestação que o texto chama de `JAGUARA`, 23,3 GWh.

    Sai `provavel`, e não `casado`, porque o cadastro abrevia os **dois** terminais:
    `JAGUARA-345` contra `JAGUARA`, e `L.C.BARRETO` contra `LUIZ CARLOS BARRETO`. Token em
    comum sem igualdade é exatamente o que `provavel` significa, e ele espera olho humano
    ([ADR 0008]). O ganho é sair de `sem_candidato`, que não dizia nada, para um candidato
    nomeado na fila de conferência.
    """
    situacao, codigos = casar(monitorado(JAGUARA), CADASTRO)

    assert (situacao, codigos) == (PROVAVEL, ["MGJGUS3USLB1SP"])


@pytest.mark.skipif(
    not __import__("pathlib").Path("dados/snapshots").is_dir(),
    reason="sem snapshot local; rode make snapshot",
)
def test_contra_o_cadastro_de_verdade() -> None:
    """O cadastro sintético acima tem de descrever o real: os códigos são os do ONS."""
    from pathlib import Path

    pastas = sorted(p for p in Path("dados/snapshots").iterdir() if p.is_dir())
    cadastro = ler_cadastro(duckdb.connect(), pastas[-1])

    for texto, esperado in ((ITABIRA, "MGIBAQ2ITB51"), (AQUIRAZ, "CEAQR-2FTZ-1")):
        situacao, codigos = casar(monitorado(texto), cadastro)
        assert (situacao, codigos) == (CASADO, [esperado]), texto[:60]
