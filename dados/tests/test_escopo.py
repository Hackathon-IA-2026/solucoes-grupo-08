"""Escopo da ingestão: só inequação que vigia linha de transmissão entra.

Os [invariantes](../../docs/invariantes.md) mandam não ingerir transformação, fluxo, interface
nem sistêmica. Até 2026-09-21 a ingestão não filtrava nada disso, e as 30 restrições fora de
escopo somavam 300,3 GWh — 4,9% do denominador de toda fatia que o produto mostra.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from arco_dados.texto import FLUXO, INDETERMINADO, LINHA, SISTEMICA, TRANSFORMACAO, escopo

DOURADO = Path(__file__).parent / "dourado_escopo.csv"


def dourado() -> list[dict[str, str]]:
    with DOURADO.open(encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.mark.parametrize("linha", dourado(), ids=lambda x: x["texto"][:60])
def test_dourado_dos_61_textos(linha: dict[str, str]) -> None:
    """Cada texto do snapshot de 2026-09-15 com a classificação conferida à mão.

    Trava a regra inteira: mudar o classificador e mover um texto de balde quebra aqui, com o
    nome do texto no relatório. Os textos moram no arquivo porque snapshot não entra no git.
    """
    assert escopo(linha["texto"]) == linha["escopo"]


def test_o_dourado_cobre_os_quatro_baldes() -> None:
    """Se um balde ficar vazio, o dourado parou de exercitar a regra que o produz."""
    baldes = {linha["escopo"] for linha in dourado()}

    assert baldes == {LINHA, TRANSFORMACAO, FLUXO, SISTEMICA}


def test_o_dourado_nao_tem_indeterminado() -> None:
    """Indeterminado no dourado é regra incompleta, não dado estranho: os 61 foram lidos."""
    assert [linha["texto"] for linha in dourado() if linha["escopo"] == INDETERMINADO] == []


def test_a_energia_de_linha_e_a_que_a_spec_mediu() -> None:
    """5.884,8 GWh, contra 6.185,1 antes do filtro. A spec 14 foi escrita sobre este número."""
    soma = sum(float(x["gwh"]) for x in dourado() if x["escopo"] == LINHA)

    assert soma == pytest.approx(5884.8, abs=0.1)
    assert sum(float(x["gwh"]) for x in dourado()) == pytest.approx(6185.1, abs=0.1)


def test_o_sujeito_decide_e_nao_a_palavra_no_texto() -> None:
    """O caso que o produto errava: cita LT e vigia transformador.

    Antes do filtro esta restrição entrava como linha, e o regex marcava a LT **contingenciada**
    como monitorada. O usuário poderia pedir adição de circuito nela para aliviar um
    transformador, efeito que o motor não modela.
    """
    texto = (
        "Controle de inequação: CONTROLE DE CARREGAMENTO DA TRANSFORMAÇÃO 500/230 KV DA SE SÃO "
        "JOÃO DO PIAUÍ PARA CONTINGÊNCIA DA LT 500 KV CURRAL NOVO DO PIAUÍ II / SÃO JOÃO DO "
        "PIAUÍ - C1(C1) - IO-ON.NE.2OE"
    )

    assert escopo(texto) == TRANSFORMACAO


def test_contingencia_de_transformador_nao_tira_a_linha_do_escopo() -> None:
    """O espelho do caso acima: vigia LT, a contingência é que é transformação."""
    texto = (
        "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV CHAPADA I / CURRAL NOVO "
        "DO PIAUÍ II – C1(L3) PARA CONTINGÊNCIA DA TRANSFORMAÇÃO 500/230 KV DA SE SÃO JOÃO DO "
        "PIAUÍ - IO-ON.NE.2OE"
    )

    assert escopo(texto) == LINHA


def test_sistemica_sai_mesmo_nomeando_uma_linha() -> None:
    """O ONS marca no próprio texto, e o invariante manda deixar fora."""
    texto = (
        "Controle de inequação: DESENERGIZAÇÃO DA LT 500 KV RIO DAS ÉGUAS / BARREIRAS II – "
        "C1(N2) OU C2(N5) (SISTÊMICO) - IO-PM.NE.5NE"
    )

    assert escopo(texto) == SISTEMICA


def test_texto_sem_forma_conhecida_fica_indeterminado() -> None:
    """Indeterminado é resposta, não falha: o texto sai listado pelo preparo em vez de sumir."""
    assert escopo("Alguma coisa que o ONS nunca escreveu") == INDETERMINADO
