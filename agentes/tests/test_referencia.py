"""A árvore de referência, regra 6: grade, ponto de apoio e durações, decididos por código."""

from __future__ import annotations

import asyncio
from typing import Any

from arco_agentes.explorador import RevisaoNaSituacao, Situacao
from arco_agentes.referencia import ArvoreDeReferencia

FAIXA = {
    "potencia_mw": {"minimo": 25.0, "maximo": 400.0},
    "duracao_horas": {"minimo": 2.0, "maximo": 6.0},
    "subestacoes": ["ACU III", "JAGUARUANA II"],
    "ganho_limite_mw": None,
}


def _revisao(revisao_id: int, potencia: float, fracao: float, **extra: Any) -> RevisaoNaSituacao:
    configuracao = {
        "modalidade": "bateria",
        "bateria": {
            "potencia_mw": potencia,
            "capacidade_mwh": potencia * 4,
            "subestacao": "ACU III",
        },
        "financeira": {"cenario": "referencia"},
    } | extra
    return RevisaoNaSituacao(
        revisao_id=revisao_id,
        posicao=revisao_id,
        revisao_anterior_id=None if revisao_id == 1 else 1,
        procedencia="por_agente",
        da_exploracao=revisao_id != 1,
        alavanca="",
        configuracao=configuracao,
        resultado={"fracao_recuperada": fracao},
        diagnosticos=None,
        nota=None,
    )


def _situacao(
    revisoes: list[RevisaoNaSituacao], ultimo_lote: dict | None = None, faixa=FAIXA
) -> Situacao:  # type: ignore[no-untyped-def,type-arg]
    return Situacao(
        tarefa_id=7,
        simulacao_id=1,
        rodada=1,
        pedido="x",
        teto=30,
        prontas=0,
        revisao_partida_id=1,
        faixa=faixa,
        revisoes=revisoes,
        cruzamentos=None,
        ultimo_lote=ultimo_lote,
    )


def test_grade_ponto_de_apoio_e_duracoes() -> None:
    """Partida de 50 MW com 10 % recuperados. A grade: 75, 100, 150, 200, 300 e 400 MW, mais a
    outra subestação. Frações: 20 % (+10 pontos), 28 % (+8), 34 % (+6), 37 % (+3), 40 % (+3) e
    41 % (+1). O maior tamanho em que ainda subiu 5 pontos ou mais é 150 MW, a rev 4: as
    durações de 2 e 6 h nascem dela."""
    arvore = ArvoreDeReferencia()
    partida = _revisao(1, 50, 0.10)

    primeira = asyncio.run(arvore.decidir(_situacao([partida])))

    assert primeira.acao == "disparar"
    assert [(v.alavanca, v.valor) for v in primeira.variacoes] == [
        ("bateria.potencia_mw", 75.0),
        ("bateria.potencia_mw", 100.0),
        ("bateria.potencia_mw", 150.0),
        ("bateria.potencia_mw", 200.0),
        ("bateria.potencia_mw", 300.0),
        ("bateria.potencia_mw", 400.0),
        ("bateria.subestacao", "JAGUARUANA II"),
    ]

    grade = [
        _revisao(i, p, f)
        for i, (p, f) in enumerate(
            [(75, 0.20), (100, 0.28), (150, 0.34), (200, 0.37), (300, 0.40), (400, 0.41)], start=2
        )
    ]
    lote = {
        "rodada": 1,
        "desfechos": [
            {"alavanca": "bateria.potencia_mw", "valor": r.configuracao["bateria"]["potencia_mw"],
             "estado": "pronta", "revisao_id": r.revisao_id}
            for r in grade
        ],
    }  # fmt: skip
    segunda = asyncio.run(arvore.decidir(_situacao([partida, *grade], lote)))

    assert segunda.revisao_partida_id == 4
    assert [(v.alavanca, v.valor) for v in segunda.variacoes] == [
        ("bateria.duracao_horas", 2.0),
        ("bateria.duracao_horas", 6.0),
    ]
    terceira = asyncio.run(arvore.decidir(_situacao([partida, *grade], None)))
    assert terceira.acao == "encerrar"


def test_sem_degrau_que_suba_o_apoio_e_a_partida() -> None:
    arvore = ArvoreDeReferencia()
    partida = _revisao(1, 50, 0.10)
    asyncio.run(arvore.decidir(_situacao([partida])))
    grade = [_revisao(2, 75, 0.12), _revisao(3, 100, 0.13)]
    lote = {
        "rodada": 1,
        "desfechos": [
            {"alavanca": "bateria.potencia_mw", "valor": 75, "estado": "pronta", "revisao_id": 2},
            {"alavanca": "bateria.potencia_mw", "valor": 100, "estado": "pronta", "revisao_id": 3},
        ],
    }

    segunda = asyncio.run(arvore.decidir(_situacao([partida, *grade], lote)))

    assert segunda.revisao_partida_id == 1


def test_combinada_varia_o_ganho_antes_da_bateria() -> None:
    """Na ordem em que o motor calcula: primeiro o circuito, depois a bateria."""
    faixa = FAIXA | {"ganho_limite_mw": {"minimo": 40.0, "maximo": 3005.0}}
    partida = _revisao(
        1,
        50,
        0.10,
        modalidade="combinada",
        equipamento={"cod_equipamento": "LT-1", "ganho_limite_mw": 40.0},
    )
    arvore = ArvoreDeReferencia()

    primeira = asyncio.run(arvore.decidir(_situacao([partida], faixa=faixa)))
    segunda = asyncio.run(arvore.decidir(_situacao([partida], faixa=faixa)))

    assert {v.alavanca for v in primeira.variacoes} == {"equipamento.ganho_limite_mw"}
    assert [v.valor for v in primeira.variacoes] == [60.0, 80.0, 120.0, 160.0, 240.0, 320.0]
    assert "bateria.potencia_mw" in {v.alavanca for v in segunda.variacoes}
