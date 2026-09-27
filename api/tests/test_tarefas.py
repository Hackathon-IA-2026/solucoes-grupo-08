"""Tarefa de exploração, eventos, streaming e rota de variação (feature 17, tasks 17.9, 17.12 e
17.20).

Roda em SQLite sem configuração e em Postgres com `ARCO_TEST_DATABASE_URL`, como a suíte de
carga e rotas, de onde vêm o banco e os artefatos. A restrição da fixture tem uma linha de
500 kV, 210 km e 3.005 MVA, entre JAGUARUANA II e ACU III.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import socket
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from arco_api import banco, tarefas
from arco_api.modelos import Evento, Tarefa, VinculoRestricaoEquipamento

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
RESTRICAO = carga_e_rotas.RESTRICAO
EQUIPAMENTO = carga_e_rotas.EQUIPAMENTO

FINANCEIRA: dict[str, Any] = {
    "cenario": "referencia",
    "taxa_desconto_aa": 0.08,
    "horizonte_anos": 20,
    "capex_reais": 275_000_000.0,
}
BATERIA_50_MW: dict[str, Any] = {
    "restricao_id": RESTRICAO,
    "nome": "Bateria em Açu III",
    "configuracao": {
        "modalidade": "bateria",
        "bateria": {"subestacao": "ACU III", "potencia_mw": 50.0, "capacidade_mwh": 200.0},
        "financeira": FINANCEIRA,
    },
}
"""50 MW e 4 h, com o investimento que o custo unitário de referência dá: 200.000 kWh x
1.375 R$/kWh = 275 milhões."""


@pytest.fixture
def partida(aprovado: TestClient) -> dict[str, Any]:
    return aprovado.post("/simulacoes", json=BATERIA_50_MW).json()


@pytest.fixture(autouse=True)
def disparos() -> Iterator[list[int]]:
    """O processo de `agentes` trocado por uma lista: cada tarefa disparada entra nela."""
    from arco_api.main import app

    disparadas: list[int] = []
    app.dependency_overrides[tarefas.disparador] = lambda: disparadas.append
    yield disparadas
    app.dependency_overrides.pop(tarefas.disparador, None)


def _explorador_fora(motivo: str) -> None:
    from arco_api.main import app

    def disparar(tarefa_id: int) -> None:
        raise tarefas.ExploradorFora(motivo)

    app.dependency_overrides[tarefas.disparador] = lambda: disparar


def _tarefa(cliente: TestClient, partida: dict[str, Any], **pedido: Any) -> dict[str, Any]:
    resposta = cliente.post(
        f"/simulacoes/{partida['simulacao_id']}/tarefas",
        json={"pedido": "Onde a curva de fração recuperada achata?"} | pedido,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _variar(
    cliente: TestClient,
    partida: dict[str, Any],
    tarefa: dict[str, Any],
    alavanca: str = "bateria.potencia_mw",
    valor: float | str = 100.0,
    **extra: Any,
):  # type: ignore[no-untyped-def]
    return cliente.post(
        f"/simulacoes/{partida['simulacao_id']}/variacoes",
        json={
            "tarefa_id": tarefa["id"],
            "revisao_base_id": partida["id"],
            "alavanca": alavanca,
            "valor": valor,
            "nota": "Rodada 1: a grade de tamanhos mostra onde a curva achata.",
        }
        | extra,
    )


def _tipos(tarefa_id: int) -> list[str]:
    with banco.sessao() as s:
        return list(
            s.scalars(select(Evento.tipo).where(Evento.tarefa_id == tarefa_id).order_by(Evento.id))
        )


def test_tarefa_nasce_com_a_faixa_da_partida_e_contagem_zerada(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    """Faixa da regra 7 sobre 50 MW: potência de 25 a 400 MW (8 vezes, abaixo do teto de
    3.005), duração de 2 a 6 h, subestações nos dois terminais."""
    tarefa = _tarefa(aprovado, partida)

    assert tarefa["estado"] == "em_andamento"
    assert (tarefa["teto"], tarefa["revisao_partida_id"]) == (30, partida["id"])
    assert tarefa["faixa"]["potencia_mw"] == {"minimo": 25.0, "maximo": 400.0}
    assert tarefa["faixa"]["duracao_horas"] == {"minimo": 2.0, "maximo": 6.0}
    assert tarefa["faixa"]["subestacoes"] == ["ACU III", "JAGUARUANA II"]
    assert tarefa["faixa"]["ganho_limite_mw"] is None
    assert tarefa["contagem"] == {
        "rodadas": 0,
        "disparadas": 0,
        "trabalhando": 0,
        "prontas": 0,
        "recusadas": 0,
        "interrompidas": 0,
    }


def test_segunda_tarefa_na_mesma_simulacao_e_409_com_o_id(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    primeira = _tarefa(aprovado, partida)

    segunda = aprovado.post(
        f"/simulacoes/{partida['simulacao_id']}/tarefas", json={"pedido": "de novo"}
    )

    assert segunda.status_code == 409
    assert segunda.json()["detail"]["tarefa_id"] == primeira["id"]


def test_teto_acima_de_30_nao_cria(aprovado: TestClient, partida: dict[str, Any]) -> None:
    resposta = aprovado.post(
        f"/simulacoes/{partida['simulacao_id']}/tarefas", json={"pedido": "x", "teto": 31}
    )
    assert resposta.status_code == 422


def test_criar_a_tarefa_poe_o_explorador_para_rodar(
    aprovado: TestClient, partida: dict[str, Any], disparos: list[int]
) -> None:
    """Só o `pedido` basta: o resto sai da revisão mais nova, e a API dispara a exploração."""
    tarefa = _tarefa(aprovado, partida)

    assert disparos == [tarefa["id"]]


def test_quem_roda_o_proprio_explorador_nao_dispara(
    aprovado: TestClient, partida: dict[str, Any], disparos: list[int]
) -> None:
    tarefa = _tarefa(aprovado, partida, disparar=False)

    assert tarefa["estado"] == "em_andamento"
    assert disparos == []


def test_explorador_fora_do_ar_da_503_e_nao_trava_a_simulacao(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    """Sem isto a tarefa ficaria 20 minutos em andamento, sem rodada, e a simulação em `409`."""
    _explorador_fora("o processo de agentes não respondeu")

    resposta = aprovado.post(
        f"/simulacoes/{partida['simulacao_id']}/tarefas", json={"pedido": "Onde achata?"}
    )

    assert resposta.status_code == 503
    detalhe = resposta.json()["detail"]
    assert detalhe["mensagem"] == "o processo de agentes não respondeu"
    vista = aprovado.get(f"/tarefas/{detalhe['tarefa_id']}").json()
    assert vista["estado"] == "falhou"
    assert vista["erro"] == "a exploração não começou: o processo de agentes não respondeu"
    assert _tipos(detalhe["tarefa_id"]) == ["tarefa_terminada"]

    _explorador_fora("de novo fora")
    de_novo = aprovado.post(
        f"/simulacoes/{partida['simulacao_id']}/tarefas", json={"pedido": "Onde achata?"}
    )
    assert de_novo.status_code == 503, "a primeira não ficou aberta segurando um 409"


def _porta_fechada() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_disparo_por_http_diz_por_que_nao_comecou(monkeypatch: pytest.MonkeyPatch) -> None:
    porta = _porta_fechada()
    monkeypatch.setenv("ARCO_AGENTES_URL", f"http://127.0.0.1:{porta}")
    with pytest.raises(tarefas.ExploradorFora, match=f"não respondeu em http://127.0.0.1:{porta}"):
        tarefas._disparar_por_http(7)

    recusa = httpx.Response(503, json={"detail": "sem GEMINI_API_KEY, o explorador não roda"})
    monkeypatch.setattr(tarefas.httpx, "post", lambda url, timeout: recusa)
    with pytest.raises(tarefas.ExploradorFora, match="recusou \\(503: sem GEMINI_API_KEY"):
        tarefas._disparar_por_http(7)

    aceita = httpx.Response(202, json={"tarefa_id": 7})
    chamadas: list[str] = []

    def post(url: str, timeout: float) -> httpx.Response:
        chamadas.append(url)
        return aceita

    monkeypatch.setattr(tarefas.httpx, "post", post)
    tarefas._disparar_por_http(7)
    assert chamadas == [f"http://127.0.0.1:{porta}/exploracoes/7"]


def test_resumo_mostra_o_que_varia_e_o_que_fica(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    """O que a pessoa confirma: sem preço na partida, vale a premissa de 216 R$/MWh."""
    resumo = aprovado.get(f"/simulacoes/{partida['simulacao_id']}/exploracao").json()

    assert resumo["revisao_partida_id"] == partida["id"]
    assert resumo["configuracao"]["bateria"]["potencia_mw"] == 50
    fixas = resumo["condicoes_fixas"]
    assert (fixas["cenario"], fixas["taxa_desconto_aa"]) == ("referencia", 0.08)
    assert (fixas["preco_energia_reais_mwh"], fixas["preco_da_premissa"]) == (216.0, True)
    assert [c["id"] for c in fixas["custos_unitarios"]] == ["bateria_capex_kwh"]
    assert resumo["teto_maximo"] == 30
    assert _nenhuma_tarefa(), "o resumo não cria nada"


def _nenhuma_tarefa() -> bool:
    with banco.sessao() as s:
        return s.scalars(select(Tarefa)).first() is None


def test_estreitar_na_confirmacao(aprovado: TestClient, partida: dict[str, Any]) -> None:
    """ "Varia só a potência." Alavanca que a modalidade não tem é 422, não faixa alargada."""
    tarefa = _tarefa(aprovado, partida, alavancas=["bateria.potencia_mw"])
    assert tarefa["faixa"]["duracao_horas"] is None

    duracao = _variar(aprovado, partida, tarefa, "bateria.duracao_horas", 6.0)
    assert duracao.status_code == 422
    assert "não varia essa alavanca" in duracao.text

    resumo = aprovado.get(
        f"/simulacoes/{partida['simulacao_id']}/exploracao",
        params={"alavancas": ["equipamento.ganho_limite_mw"]},
    )
    assert resumo.status_code == 422


def test_variacao_salva_revisao_por_agente_com_a_conta_e_os_eventos(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    """50 para 100 MW em 4 h: capex de 275 para 550 milhões, pela conta que vai nos avisos."""
    tarefa = _tarefa(aprovado, partida)

    resposta = _variar(aprovado, partida, tarefa, variacao_id="r1-v1", rodada=1)

    assert resposta.status_code == 200, resposta.text
    salva = resposta.json()
    assert (salva["procedencia"], salva["revisao_anterior_id"]) == ("por_agente", partida["id"])
    assert salva["nota"].startswith("Rodada 1")
    inteira = aprovado.get(f"/simulacoes/{salva['id']}").json()
    assert inteira["configuracao"]["bateria"]["capacidade_mwh"] == pytest.approx(400)
    assert inteira["configuracao"]["financeira"]["capex_reais"] == pytest.approx(550_000_000)
    assert "investimento_por_custo_unitario" in [a["codigo"] for a in inteira["avisos"]]

    assert _tipos(tarefa["id"]) == [
        "variacao_iniciada",
        "variacao_passo",
        "variacao_passo",
        "variacao_passo",
        "revisao_pronta",
    ]
    vista = aprovado.get(f"/tarefas/{tarefa['id']}").json()
    assert vista["contagem"]["prontas"] == 1
    assert vista["contagem"]["trabalhando"] == 0
    assert vista["revisoes"] == [salva["id"]]


def test_variacoes_irmas_comparam_com_a_mesma_origem(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    tarefa = _tarefa(aprovado, partida)
    maior = _variar(aprovado, partida, tarefa, valor=100.0).json()
    duracao = _variar(aprovado, partida, tarefa, "bateria.duracao_horas", 6.0).json()

    assert maior["revisao_anterior_id"] == duracao["revisao_anterior_id"] == partida["id"]
    revisoes = aprovado.get("/simulacoes").json()[0]["revisoes"]
    por_id = {r["id"]: r["o_que_mudou"] for r in revisoes}
    assert por_id[duracao["id"]].startswith("Capacidade da bateria: 200 → 300")


def test_variacao_repetida_e_409_e_conta_como_recusada(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    tarefa = _tarefa(aprovado, partida)
    assert _variar(aprovado, partida, tarefa, valor=100.0).status_code == 200

    repetida = _variar(aprovado, partida, tarefa, valor=100.0)

    assert repetida.status_code == 409
    assert "igual à da revisão" in repetida.text
    contagem = aprovado.get(f"/tarefas/{tarefa['id']}").json()["contagem"]
    assert (contagem["prontas"], contagem["recusadas"], contagem["disparadas"]) == (1, 1, 2)


def test_variacao_igual_a_partida_e_repetida(aprovado: TestClient, partida: dict[str, Any]) -> None:
    tarefa = _tarefa(aprovado, partida)
    assert _variar(aprovado, partida, tarefa, valor=50.0).status_code == 409


def test_fora_da_faixa_e_422_com_o_limite(aprovado: TestClient, partida: dict[str, Any]) -> None:
    tarefa = _tarefa(aprovado, partida)

    resposta = _variar(aprovado, partida, tarefa, valor=500.0)

    assert resposta.status_code == 422
    assert "de 25 a 400 MW" in resposta.text
    assert _tipos(tarefa["id"])[-1] == "variacao_recusada"


def test_teto_atingido_salva_so_o_que_cabe(aprovado: TestClient, partida: dict[str, Any]) -> None:
    tarefa = _tarefa(aprovado, partida, teto=1)
    assert _variar(aprovado, partida, tarefa, valor=100.0).status_code == 200

    acima = _variar(aprovado, partida, tarefa, valor=150.0)

    assert acima.status_code == 409
    assert "teto de 1 revisões" in acima.text
    assert len(aprovado.get(f"/simulacoes/{partida['id']}").json()["revisoes"]) == 2


@pytest.mark.parametrize(
    "campo",
    [
        {"preco_energia_reais_mwh": 400.0},
        {"taxa_desconto_aa": 0.05},
        {"cenario": "otimista"},
        {"configuracao": BATERIA_50_MW["configuracao"]},
    ],
)
def test_nenhum_campo_financeiro_entra_na_variacao(
    aprovado: TestClient, partida: dict[str, Any], campo: dict[str, Any]
) -> None:
    """Condição fixa por construção: o pedido não tem por onde mudar preço, taxa ou cenário."""
    tarefa = _tarefa(aprovado, partida)

    resposta = _variar(aprovado, partida, tarefa, **campo)

    assert resposta.status_code == 422
    assert len(aprovado.get(f"/simulacoes/{partida['id']}").json()["revisoes"]) == 1


def test_variacao_herda_a_fonte_da_partida(
    aprovado_com_solar: TestClient,
) -> None:
    """Fonte e correção de minutos são premissa, não campo: a variação calcula com as da
    partida, senão compararia séries diferentes."""
    salva = aprovado_com_solar.post(
        "/simulacoes", json=BATERIA_50_MW | {"fonte": "ambas", "correcao_minutos": False}
    ).json()
    tarefa = _tarefa(aprovado_com_solar, salva)

    variada = _variar(aprovado_com_solar, salva, tarefa, valor=100.0).json()

    usadas = aprovado_com_solar.get(f"/simulacoes/{variada['id']}").json()["premissas_usadas"]
    assert usadas["fonte_geracao"]["valor"] == "ambas"
    assert usadas["correcao_minutos"]["valor"] is False


aprovado_com_solar = carga_e_rotas.aprovado_com_solar


def test_ganho_na_contingenciada_e_recusado(aprovado: TestClient) -> None:
    """A partida foi salva quando a linha era a monitorada; depois o texto a pôs como
    contingenciada. A variação passa pelas mesmas conferências de salvar."""
    circuito = aprovado.post(
        "/simulacoes",
        json={
            "restricao_id": RESTRICAO,
            "nome": "Circuito",
            "configuracao": {
                "modalidade": "equipamento",
                "equipamento": {
                    "tipo": "adicao_circuito",
                    "cod_equipamento": EQUIPAMENTO,
                    "ganho_limite_mw": 40.0,
                },
                "financeira": FINANCEIRA,
            },
        },
    ).json()
    tarefa = _tarefa(aprovado, circuito)
    with banco.sessao() as s:
        s.scalars(select(VinculoRestricaoEquipamento)).one().papel = "contingenciado"
        s.commit()

    resposta = _variar(aprovado, circuito, tarefa, "equipamento.ganho_limite_mw", 60.0)

    assert resposta.status_code == 422
    assert "não recebe circuito novo" in resposta.text


def test_tarefa_de_outra_simulacao_e_422(aprovado: TestClient, partida: dict[str, Any]) -> None:
    outra = aprovado.post("/simulacoes", json=BATERIA_50_MW | {"nome": "Outra"}).json()
    tarefa_da_outra = _tarefa(aprovado, outra)

    resposta = _variar(aprovado, partida, tarefa_da_outra)

    assert resposta.status_code == 422


def test_eventos_do_agente_e_o_fim_da_tarefa(aprovado: TestClient, partida: dict[str, Any]) -> None:
    tarefa = _tarefa(aprovado, partida)
    eventos = f"/tarefas/{tarefa['id']}/eventos"

    rodada = aprovado.post(
        eventos,
        json={
            "tipo": "rodada_decidida",
            "rodada": 1,
            "revisao_partida_id": partida["id"],
            "porque": "A grade de tamanhos mostra onde a curva achata.",
            "variacoes": [{"alavanca": "bateria.potencia_mw", "valor": 100}],
        },
    )
    assert rodada.status_code == 201, rodada.text
    fim = aprovado.post(
        eventos,
        json={"tipo": "tarefa_terminada", "estado": "concluida", "motivo": "A curva achatou."},
    )
    assert fim.status_code == 201

    vista = aprovado.get(f"/tarefas/{tarefa['id']}").json()
    assert (vista["estado"], vista["motivo"]) == ("concluida", "A curva achatou.")
    assert vista["terminada_em"] is not None
    assert vista["contagem"]["rodadas"] == 1
    depois = aprovado.post(
        eventos,
        json={"tipo": "tarefa_terminada", "estado": "falhou", "motivo": "de novo"},
    )
    assert depois.status_code == 409
    assert _variar(aprovado, partida, tarefa).status_code == 409
    assert _tarefa(aprovado, partida)["id"] != tarefa["id"], "terminada libera a simulação"


def test_eventos_da_variacao_nao_entram_pela_rota_do_agente(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    """`revisao_pronta` de fora inflaria a contagem: só a rota que salva o grava."""
    tarefa = _tarefa(aprovado, partida)

    resposta = aprovado.post(
        f"/tarefas/{tarefa['id']}/eventos",
        json={"tipo": "revisao_pronta", "variacao_id": "x", "revisao_id": partida["id"]},
    )

    assert resposta.status_code == 422


def test_relatorio_de_outra_simulacao_nao_se_liga(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    tarefa = _tarefa(aprovado, partida)

    resposta = aprovado.post(
        f"/tarefas/{tarefa['id']}/eventos", json={"tipo": "relatorio_pedido", "relatorio_id": 999}
    )

    assert resposta.status_code == 422


def test_tarefa_parada_ha_mais_de_20_minutos_vira_falhou(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    tarefa = _tarefa(aprovado, partida)
    with banco.sessao() as s:
        linha = s.get(Tarefa, tarefa["id"])
        assert linha is not None
        linha.criada_em = datetime.now(UTC) - timedelta(minutes=21)
        s.commit()

    vista = aprovado.get(f"/tarefas/{tarefa['id']}").json()

    assert vista["estado"] == "falhou"
    assert "sem evento" in vista["erro"]
    assert _tipos(tarefa["id"]) == ["tarefa_terminada"]
    assert _tarefa(aprovado, partida)["estado"] == "em_andamento", "a simulação fica livre"


def _gravado(id: int, dados: dict[str, Any]) -> tarefas.EventoGravado:
    return tarefas.EventoGravado.model_validate(
        {"id": id, "tarefa_id": 1, "instante": datetime(2026, 9, 23, tzinfo=UTC), "evento": dados}
    )


def test_contagem_nao_depende_da_ordem_de_chegada() -> None:
    """Três variações: uma pronta, uma recusada pela rota, uma ainda trabalhando; mais uma
    recusa do agente antes da rota. Em qualquer ordem, a mesma contagem."""
    eventos = [
        {"tipo": "variacao_iniciada", "variacao_id": "a", "rodada": 1, "revisao_partida_id": 1,
         "alavanca": "bateria.potencia_mw", "valor": 100},
        {"tipo": "revisao_pronta", "variacao_id": "a", "revisao_id": 2},
        {"tipo": "variacao_iniciada", "variacao_id": "b", "rodada": 1, "revisao_partida_id": 1,
         "alavanca": "bateria.potencia_mw", "valor": 150},
        {"tipo": "variacao_recusada", "variacao_id": "b", "motivo": "repetida", "status": 409},
        {"tipo": "variacao_passo", "variacao_id": "c", "passo": "calculando"},
        {"tipo": "variacao_recusada", "motivo": "duas alavancas"},
    ]  # fmt: skip
    esperada = tarefas.Contagem(
        rodadas=0, disparadas=3, trabalhando=1, prontas=1, recusadas=2, interrompidas=0
    )
    for ordem in itertools.permutations(eventos):
        gravados = [_gravado(i, dados) for i, dados in enumerate(ordem, start=1)]
        assert tarefas.contar(gravados, terminada=False) == esperada
    terminada = tarefas.contar([_gravado(i, d) for i, d in enumerate(eventos, 1)], terminada=True)
    assert (terminada.trabalhando, terminada.interrompidas) == (0, 1)


def _mensagens(corpo: str) -> list[dict[str, Any]]:
    return [
        json.loads(linha.removeprefix("data: "))
        for linha in corpo.splitlines()
        if linha.startswith("data: ")
    ]


def test_streaming_manda_os_gravados_e_fecha_quando_a_tarefa_termina(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    tarefa = _tarefa(aprovado, partida)
    _variar(aprovado, partida, tarefa, variacao_id="v1")
    aprovado.post(
        f"/tarefas/{tarefa['id']}/eventos",
        json={"tipo": "tarefa_terminada", "estado": "concluida", "motivo": "fim"},
    )

    resposta = aprovado.get(f"/tarefas/{tarefa['id']}/eventos")

    assert resposta.headers["content-type"].startswith("text/event-stream")
    tipos = [m["evento"]["tipo"] for m in _mensagens(resposta.text)]
    assert tipos == [*_tipos(tarefa["id"])]
    assert tipos[-1] == "tarefa_terminada"
    assert "event: revisao_pronta" in resposta.text

    ids = [m["id"] for m in _mensagens(resposta.text)]
    retomada = aprovado.get(
        f"/tarefas/{tarefa['id']}/eventos", headers={"Last-Event-ID": str(ids[2])}
    )
    assert [m["id"] for m in _mensagens(retomada.text)] == ids[3:]


def test_streaming_entrega_o_evento_gravado_depois_de_conectar(
    aprovado: TestClient, partida: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A conexão abre com a tarefa em andamento e sem nada; a variação e o fim chegam depois. O
    cliente de teste só devolve o corpo quando o streaming fecha, e ele tem de ter tudo."""
    monkeypatch.setattr(tarefas, "INTERVALO_DO_STREAMING_S", 0.02)
    tarefa = _tarefa(aprovado, partida)
    recebido: dict[str, str] = {}

    def seguir() -> None:
        recebido["corpo"] = aprovado.get(f"/tarefas/{tarefa['id']}/eventos").text

    leitor = threading.Thread(target=seguir)
    leitor.start()
    _variar(aprovado, partida, tarefa, variacao_id="depois")
    aprovado.post(
        f"/tarefas/{tarefa['id']}/eventos",
        json={"tipo": "tarefa_terminada", "estado": "concluida", "motivo": "fim"},
    )
    leitor.join(timeout=30)

    assert not leitor.is_alive(), "o streaming não fechou com a tarefa terminada"
    tipos = [m["evento"]["tipo"] for m in _mensagens(recebido["corpo"])]
    assert "revisao_pronta" in tipos
    assert tipos[-1] == "tarefa_terminada"


def test_streaming_de_tarefa_que_nao_existe_e_404(aprovado: TestClient) -> None:
    assert aprovado.get("/tarefas/999/eventos").status_code == 404


def test_revisao_pronta_traz_o_bastante_para_desenhar_a_caixa(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    """Posição, origem, rodada, alavanca e o resumo do resultado vão no evento: a tela não
    precisa buscar a revisão, que traz a série inteira de cada meia hora."""
    tarefa = _tarefa(aprovado, partida)
    salva = _variar(aprovado, partida, tarefa, variacao_id="r1-v1", rodada=1).json()
    corpo = aprovado.post(
        f"/tarefas/{tarefa['id']}/eventos",
        json={"tipo": "tarefa_terminada", "estado": "concluida", "motivo": "fim"},
    )
    assert corpo.status_code == 201
    (pronta,) = [
        m["evento"]
        for m in _mensagens(aprovado.get(f"/tarefas/{tarefa['id']}/eventos").text)
        if m["evento"]["tipo"] == "revisao_pronta"
    ]
    inteira = aprovado.get(f"/simulacoes/{salva['id']}").json()
    assert pronta["revisao_id"] == salva["id"]
    assert pronta["posicao"] == 2
    assert pronta["revisao_partida_id"] == partida["id"]
    assert (pronta["rodada"], pronta["alavanca"], pronta["valor"]) == (
        1,
        "bateria.potencia_mw",
        100.0,
    )
    resumo = pronta["resumo"]
    assert resumo["vpl_reais"] == pytest.approx(inteira["resultado"]["financeiro"]["vpl_reais"])
    assert resumo["fracao_recuperada"] == pytest.approx(
        inteira["resultado"]["tecnico"]["fracao_recuperada"]
    )
    assert resumo["avisos"] == len(inteira["avisos"])


def test_listar_tarefas_da_simulacao_da_mais_nova(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    primeira = _tarefa(aprovado, partida)
    aprovado.post(
        f"/tarefas/{primeira['id']}/eventos",
        json={"tipo": "tarefa_terminada", "estado": "concluida", "motivo": "fim"},
    )
    segunda = _tarefa(aprovado, partida)
    lista = aprovado.get(f"/simulacoes/{partida['simulacao_id']}/tarefas").json()
    assert [(t["id"], t["estado"]) for t in lista] == [
        (segunda["id"], "em_andamento"),
        (primeira["id"], "concluida"),
    ]
    assert aprovado.get("/simulacoes/999/tarefas").status_code == 404


def test_decidindo_rodada_e_gravado_e_nao_conta_como_rodada(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    """A rodada só conta quando decidida; enquanto o agente pensa, a tela mostra que ele pensa."""
    tarefa = _tarefa(aprovado, partida)
    resposta = aprovado.post(
        f"/tarefas/{tarefa['id']}/eventos", json={"tipo": "decidindo_rodada", "rodada": 1}
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["evento"] == {"tipo": "decidindo_rodada", "rodada": 1}
    assert aprovado.get(f"/tarefas/{tarefa['id']}").json()["contagem"]["rodadas"] == 0


def test_nada_e_gravado_depois_de_tarefa_terminada(
    aprovado: TestClient, partida: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tarefa termina com uma variação no meio do cálculo. O passo e a recusa que viriam depois
    não entram: `tarefa_terminada` fica o último evento, e o streaming, que fecha nele, não perde
    nada."""
    tarefa = _tarefa(aprovado, partida)
    calcular = tarefas.calcular

    def termina_no_meio(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        aprovado.post(
            f"/tarefas/{tarefa['id']}/eventos",
            json={"tipo": "tarefa_terminada", "estado": "falhou", "motivo": "parada no meio"},
        )
        return calcular(*args, **kwargs)

    monkeypatch.setattr(tarefas, "calcular", termina_no_meio)
    resposta = _variar(aprovado, partida, tarefa, variacao_id="no-meio")

    assert resposta.status_code == 409
    tipos = _tipos(tarefa["id"])
    assert tipos[-1] == "tarefa_terminada"
    assert "revisao_pronta" not in tipos
    vista = aprovado.get(f"/tarefas/{tarefa['id']}").json()
    assert vista["contagem"]["interrompidas"] == 1


def test_rodada_decidida_leva_o_id_de_cada_variacao(
    aprovado: TestClient, partida: dict[str, Any]
) -> None:
    tarefa = _tarefa(aprovado, partida)
    resposta = aprovado.post(
        f"/tarefas/{tarefa['id']}/eventos",
        json={
            "tipo": "rodada_decidida",
            "rodada": 1,
            "revisao_partida_id": partida["id"],
            "porque": "Grade de tamanhos.",
            "variacoes": [
                {"alavanca": "bateria.potencia_mw", "valor": 100, "variacao_id": "r1-v1"},
                {"alavanca": "bateria.potencia_mw", "valor": 150},
            ],
        },
    )
    assert resposta.status_code == 201, resposta.text
    variacoes = resposta.json()["evento"]["variacoes"]
    assert [v["variacao_id"] for v in variacoes] == ["r1-v1", None]
