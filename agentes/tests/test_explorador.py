"""O explorador por rodadas (task 17.14), com o modelo trocado por um roteiro de decisões e a API
pela falsa do `conftest.py`. O MCP é o de verdade, num `uvicorn` em thread, e o explorador fala
com ele pelo cliente MCP do Strands, no caminho do explorador, como em produção."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from arco_agentes import servidor as modulo_servidor
from arco_agentes.api import ClienteDaApi
from arco_agentes.explorador import (
    Decisao,
    Exploracao,
    Explorador,
    FerramentaRecusou,
    FerramentasDoStrands,
    Situacao,
    VariacaoDecidida,
)
from arco_agentes.referencia import ArvoreDeReferencia
from arco_agentes.servidor import Contexto, em_segundo_plano

CAMPOS_DA_VARIACAO = {
    "tarefa_id",
    "revisao_base_id",
    "alavanca",
    "valor",
    "nota",
    "variacao_id",
    "rodada",
}


class Roteiro:
    """O modelo substituído: devolve as decisões na ordem e guarda o que leu."""

    def __init__(self, *decisoes: Decisao | Exception) -> None:
        self.decisoes = list(decisoes)
        self.situacoes: list[Situacao] = []

    async def decidir(self, situacao: Situacao) -> Decisao:
        self.situacoes.append(situacao)
        decisao = self.decisoes.pop(0)
        if isinstance(decisao, Exception):
            raise decisao
        return decisao


def disparar(*variacoes: tuple[str, float | str], porque: str = "Rodada.") -> Decisao:
    return Decisao(
        acao="disparar",
        revisao_partida_id=1,
        variacoes=[VariacaoDecidida(alavanca=a, valor=v) for a, v in variacoes],  # type: ignore[arg-type]
        porque=porque,
    )


def encerrar(porque: str = "O pedido está respondido.") -> Decisao:
    return Decisao(acao="encerrar", porque=porque)


@pytest.fixture
def mcp(contexto: Contexto, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setattr(modulo_servidor, "INTERVALO_DO_RELATORIO_S", 0.0)
    with em_segundo_plano(contexto) as base:
        yield f"{base}/explorador/mcp"


@pytest.fixture
def ferramentas(mcp: str) -> Iterator[FerramentasDoStrands]:
    with FerramentasDoStrands(mcp) as abertas:
        yield abertas


def _explorar(
    api_falsa, ferramentas: FerramentasDoStrands, decisor: Any, teto: int = 30
) -> Exploracao:  # type: ignore[no-untyped-def]
    api = ClienteDaApi("http://api", transporte=httpx.MockTransport(api_falsa.responder))

    async def rodar() -> Exploracao:
        tarefa = await api.criar_tarefa(1, {"pedido": "Onde a curva achata?", "teto": teto})
        return await Explorador(api, ferramentas, decisor).explorar(tarefa["id"])

    return asyncio.run(rodar())


def test_o_explorador_so_ve_as_ferramentas_dele(ferramentas: FerramentasDoStrands) -> None:
    nomes = ferramentas.nomes()

    assert {"disparar_lote", "encerrar", "ver_revisao"} <= nomes
    assert not nomes & {"explorar_variacoes", "ver_andamento", "gerar_relatorio", "salvar_revisao"}


def test_tres_rodadas_em_paralelo_com_os_eventos_na_ordem(
    api_falsa, ferramentas: FerramentasDoStrands
) -> None:  # type: ignore[no-untyped-def]
    """Rodada 1 pede cinco: três rodam juntas, uma está fora da faixa e uma repete o lote. As
    rodadas 2 e 3 pedem uma cada, e a 4 encerra. `decidindo_rodada` antes de cada decisão,
    `rodada_decidida` antes das variações dela, `tarefa_terminada` por último."""
    api_falsa.atraso_s = 0.1
    roteiro = Roteiro(
        disparar(
            ("bateria.potencia_mw", 100),
            ("bateria.potencia_mw", 150),
            ("bateria.potencia_mw", 200),
            ("bateria.potencia_mw", 500),
            ("bateria.potencia_mw", 100),
            porque="Rodada 1: a grade de tamanhos.",
        ),
        disparar(("bateria.duracao_horas", 6), porque="Rodada 2: mais duração."),
        disparar(("bateria.subestacao", "JAGUARUANA II"), porque="Rodada 3: a outra ponta."),
        encerrar("A curva achatou entre as rev 3 e 4."),
    )

    exploracao = _explorar(api_falsa, ferramentas, roteiro)

    assert exploracao.erro is None
    assert api_falsa.tipos() == [
        "decidindo_rodada",
        "rodada_decidida",
        "variacao_recusada",
        "variacao_recusada",
        "revisao_pronta",
        "revisao_pronta",
        "revisao_pronta",
        "decidindo_rodada",
        "rodada_decidida",
        "revisao_pronta",
        "decidindo_rodada",
        "rodada_decidida",
        "revisao_pronta",
        "decidindo_rodada",
        "relatorio_pedido",
        "relatorio_pronto",
        "tarefa_terminada",
    ]
    rodadas = [e["rodada"] for e in api_falsa.eventos if e["tipo"] == "decidindo_rodada"]
    assert rodadas == [1, 2, 3, 4]
    assert api_falsa.maximo_em_curso >= 2, "o lote roda em paralelo"
    assert api_falsa.eventos[-1]["motivo"] == "A curva achatou entre as rev 3 e 4."

    enviadas = api_falsa.pedidos("POST", "/simulacoes/1/variacoes")
    assert len(enviadas) == 5
    assert all(set(p) <= CAMPOS_DA_VARIACAO for p in enviadas), "nada de preço, taxa ou cenário"
    assert roteiro.situacoes[1].ultimo_lote is not None
    assert {d["estado"] for d in roteiro.situacoes[1].ultimo_lote["desfechos"]} == {
        "pronta",
        "recusada",
    }
    assert sum(r.da_exploracao for r in roteiro.situacoes[3].revisoes) == 5


def test_teto_atingido_no_meio_do_lote_salva_o_que_cabe_e_encerra(
    api_falsa, ferramentas: FerramentasDoStrands
) -> None:  # type: ignore[no-untyped-def]
    roteiro = Roteiro(
        disparar(
            ("bateria.potencia_mw", 100), ("bateria.potencia_mw", 150), ("bateria.potencia_mw", 200)
        )
    )

    _explorar(api_falsa, ferramentas, roteiro, teto=2)

    assert len(roteiro.situacoes) == 1, "com o teto cheio, não pergunta de novo ao modelo"
    assert api_falsa.tipos().count("revisao_pronta") == 2
    assert api_falsa.eventos[-1] == {
        "tipo": "tarefa_terminada",
        "estado": "concluida",
        "motivo": "teto de 2 revisões atingido",
    }


def test_duas_rodadas_sem_revisao_nova_encerram(
    api_falsa, ferramentas: FerramentasDoStrands
) -> None:  # type: ignore[no-untyped-def]
    roteiro = Roteiro(
        disparar(("bateria.potencia_mw", 500)), disparar(("bateria.potencia_mw", 600))
    )

    _explorar(api_falsa, ferramentas, roteiro)

    assert len(roteiro.situacoes) == 2
    assert api_falsa.pedidos("POST", "/simulacoes/1/variacoes") == []
    assert api_falsa.eventos[-1]["motivo"] == "2 rodadas seguidas sem revisão nova"


def test_falha_do_decisor_termina_em_falhou_com_o_motivo(
    api_falsa, ferramentas: FerramentasDoStrands
) -> None:  # type: ignore[no-untyped-def]
    exploracao = _explorar(api_falsa, ferramentas, Roteiro(RuntimeError("modelo fora do ar")))

    assert exploracao.erro == "RuntimeError: modelo fora do ar"
    assert api_falsa.eventos[-1] == {
        "tipo": "tarefa_terminada",
        "estado": "falhou",
        "motivo": "RuntimeError: modelo fora do ar",
    }


def test_continuar_le_as_revisoes_e_notas_da_exploracao_anterior(
    api_falsa, ferramentas: FerramentasDoStrands
) -> None:  # type: ignore[no-untyped-def]
    """Continuar uma exploração que falhou é disparar de novo na mesma simulação: o decisor lê
    as revisões e as notas de antes, e a trava de revisão repetida da API impede refazer."""
    api_falsa.anteriores = {5: "Rodada 1 da exploração anterior: a grade de tamanhos."}
    roteiro = Roteiro(encerrar())

    _explorar(api_falsa, ferramentas, roteiro)

    (situacao,) = roteiro.situacoes
    anterior = next(r for r in situacao.revisoes if r.revisao_id == 5)
    assert anterior.nota == "Rodada 1 da exploração anterior: a grade de tamanhos."
    assert anterior.da_exploracao is False
    assert anterior.diagnosticos is not None


def test_variacao_com_duas_alavancas_e_recusada_sem_chamar_a_rota(
    api_falsa, ferramentas: FerramentasDoStrands
) -> None:  # type: ignore[no-untyped-def]
    asyncio.run(
        ClienteDaApi(
            "http://api", transporte=httpx.MockTransport(api_falsa.responder)
        ).criar_tarefa(1, {"pedido": "x", "teto": 30})
    )

    with pytest.raises(FerramentaRecusou, match=r"bateria\.duracao_horas"):
        asyncio.run(
            ferramentas.chamar(
                "disparar_lote",
                {
                    "tarefa_id": 7,
                    "revisao_partida_id": 1,
                    "variacoes": [
                        {
                            "alavanca": "bateria.potencia_mw",
                            "valor": 100,
                            "bateria.duracao_horas": 6,
                        }
                    ],
                    "porque": "Duas de uma vez.",
                },
            )
        )
    assert api_falsa.pedidos("POST", "/simulacoes/1/variacoes") == []


def test_arvore_de_referencia_pelo_mesmo_laco(api_falsa, ferramentas: FerramentasDoStrands) -> None:  # type: ignore[no-untyped-def]
    """Sem modelo, pelas mesmas ferramentas. Na API falsa toda revisão recupera a mesma fração,
    então nenhum degrau sobe 5 pontos: o apoio é a própria partida, de 4 h, e as durações
    testadas são 2 e 6 h."""
    exploracao = _explorar(api_falsa, ferramentas, ArvoreDeReferencia())

    assert [d["acao"] for d in exploracao.decisoes] == ["disparar", "disparar", "encerrar"]
    anunciadas = [e for e in api_falsa.eventos if e["tipo"] == "rodada_decidida"]
    grade = [(v["alavanca"], v["valor"]) for v in anunciadas[0]["variacoes"]]
    assert grade == [
        ("bateria.potencia_mw", 75.0),
        ("bateria.potencia_mw", 100.0),
        ("bateria.potencia_mw", 150.0),
        ("bateria.potencia_mw", 200.0),
        ("bateria.potencia_mw", 300.0),
        ("bateria.potencia_mw", 400.0),
        ("bateria.subestacao", "JAGUARUANA II"),
    ]
    duracoes = [
        (v["valor"], anunciadas[1]["revisao_partida_id"]) for v in anunciadas[1]["variacoes"]
    ]
    assert duracoes == [(2.0, 1), (6.0, 1)]
    assert api_falsa.eventos[-1]["estado"] == "concluida"
