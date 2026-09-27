"""A API do ARCO substituída por uma falsa, no nível do HTTP.

`agentes` não importa `arco_api`, nem no teste: a falsa responde pelas mesmas rotas, com o
formato do contrato (`contratos/openapi.json`), guarda o estado de tarefa, eventos e revisões, e
registra cada chamada para o teste conferir o que o MCP pediu.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from arco_agentes.api import ClienteDaApi
from arco_agentes.config import Configuracao
from arco_agentes.servidor import Contexto

RESTRICAO = "abc123def456"

FAIXA = {
    "potencia_mw": {"minimo": 25.0, "maximo": 400.0},
    "duracao_horas": {"minimo": 2.0, "maximo": 6.0},
    "subestacoes": ["ACU III", "JAGUARUANA II"],
    "ganho_limite_mw": None,
    "avisos": [],
}

CONFIGURACAO = {
    "modalidade": "bateria",
    "bateria": {"potencia_mw": 50.0, "capacidade_mwh": 200.0, "subestacao": "ACU III"},
    "equipamento": None,
    "financeira": {
        "cenario": "referencia",
        "taxa_desconto_aa": 0.08,
        "horizonte_anos": 20,
        "capex_reais": 275_000_000.0,
        "preco_energia_reais_mwh": None,
    },
}


def revisao_completa(
    revisao_id: int,
    simulacao_id: int = 1,
    posicao: int = 1,
    irmas: list[dict[str, Any]] | None = None,
    nota: str | None = None,
) -> dict[str, Any]:
    """No formato de `RevisaoCompleta`, com as séries que a consulta não pode repassar."""
    return {
        "id": revisao_id,
        "simulacao_id": simulacao_id,
        "nome": "Bateria em Açu III",
        "pergunta": None,
        "restricao_id": RESTRICAO,
        "snapshot_id": "2026-09-15",
        "metodo_versao": "0.10.0",
        "revisao_anterior_id": None if posicao == 1 else 1,
        "procedencia": "por_pessoa" if posicao == 1 else "por_agente",
        "nota": nota if nota is not None else (None if posicao == 1 else "Rodada 1."),
        "criada_em": "2026-09-23T20:00:00Z",
        "periodo_inicio": None,
        "periodo_fim": None,
        "configuracao": CONFIGURACAO,
        "premissas_usadas": {
            "preco_energia": {"id": "preco_energia", "valor": 216.0, "status": "proposta"}
        },
        "resultado": {
            "tecnico": {
                "cortado_mw": [100.0] * 8,
                "soc_mwh": [50.0] * 8,
                "energia_cortada_mwh": 400.0,
                "energia_recuperada_mwh": 200.0,
                "fracao_recuperada": 0.5,
            },
            "financeiro": {
                "vpl_reais": -1_000_000.0,
                "tir_aa": None,
                "payback_simples_anos": None,
                "payback_descontado_anos": None,
                "custo_por_mwh_reais": 310.0,
                "fluxos": [],
            },
            "diagnosticos": {
                "metodo_versao": "0.10.0",
                "saturacao": {
                    "meias_horas_com_corte": 8,
                    "meias_horas_cheia": 4,
                    "fracao_cheia": 0.5,
                    "episodios": 1,
                    "episodios_comecaram_vazia": 1,
                    "episodios_comecaram_com_carga": 0,
                },
                "corte_residual": {
                    "energia_mwh": 200.0,
                    "por_hora_do_dia_mwh": [0.0, 0.0, 100.0, 100.0] + [0.0] * 20,
                },
            },
        },
        "avisos": [{"codigo": "x", "mensagem": "Aviso de teste.", "premissa_id": None}],
        "revisoes": irmas or [{"id": revisao_id, "posicao": posicao, "procedencia": "por_pessoa"}],
        "cruzamentos": {"payback_no_horizonte": None, "tir_acima_da_taxa": None},
    }


@dataclass
class ApiFalsa:
    chamadas: list[tuple[str, str, Any]] = field(default_factory=list)
    eventos: list[dict[str, Any]] = field(default_factory=list)
    tarefa: dict[str, Any] | None = None
    proxima_revisao: int = 10
    repetidas: set[str] = field(default_factory=set)
    """Valores de variação que a rota recusa como repetidos (409)."""
    recusas: dict[str, tuple[int, Any]] = field(default_factory=dict)
    """Caminho → (status, detail) que a API devolve em vez do sucesso."""
    tarefa_ja_existe: bool = False
    atraso_s: float = 0.0
    """Quanto cada variação demora na rota: com atraso, dá para ver quantas correm juntas."""
    em_curso: int = 0
    maximo_em_curso: int = 0
    anteriores: dict[int, str] = field(default_factory=dict)
    """Revisões que a simulação já tinha, com a nota: a exploração anterior, por exemplo."""
    criadas: list[int] = field(default_factory=list)
    consultas_ate_terminar: int | None = None
    """Quantas vezes `GET /tarefas/7` responde em andamento antes de a exploração terminar."""

    def irmas(self) -> list[dict[str, Any]]:
        ids = [1, *self.anteriores, *self.criadas]
        return [
            {"id": i, "posicao": p, "procedencia": "por_pessoa" if i == 1 else "por_agente"}
            for p, i in enumerate(ids, start=1)
        ]

    def pedidos(self, metodo: str, caminho: str) -> list[Any]:
        return [corpo for m, c, corpo in self.chamadas if m == metodo and c == caminho]

    def tipos(self) -> list[str]:
        return [e["tipo"] for e in self.eventos]

    def _tarefa(self) -> dict[str, Any]:
        assert self.tarefa is not None
        prontas = sum(1 for e in self.eventos if e["tipo"] == "revisao_pronta")
        rodadas = sum(1 for e in self.eventos if e["tipo"] == "rodada_decidida")
        return self.tarefa | {
            "revisoes": [e["revisao_id"] for e in self.eventos if e["tipo"] == "revisao_pronta"],
            "contagem": {
                "rodadas": rodadas,
                "disparadas": 0,
                "trabalhando": 0,
                "prontas": prontas,
                "recusadas": 0,
                "interrompidas": 0,
            },
        }

    async def responder(self, pedido: httpx.Request) -> httpx.Response:
        if pedido.method == "POST" and pedido.url.path == "/simulacoes/1/variacoes":
            self.em_curso += 1
            self.maximo_em_curso = max(self.maximo_em_curso, self.em_curso)
            await asyncio.sleep(self.atraso_s)
            self.em_curso -= 1
        return self._responder(pedido)

    def _responder(self, pedido: httpx.Request) -> httpx.Response:
        caminho = pedido.url.path
        corpo = json.loads(pedido.content) if pedido.content else dict(pedido.url.params)
        self.chamadas.append((pedido.method, caminho, corpo))
        if caminho in self.recusas:
            status, detalhe = self.recusas[caminho]
            return httpx.Response(status, json={"detail": detalhe})
        chave = (pedido.method, caminho)

        if chave == ("GET", "/restricoes"):
            return httpx.Response(
                200,
                json={
                    "resumo": {
                        "fonte": "eolica",
                        "snapshot_id": "2026-09-15",
                        "restricoes": 1,
                        "energia_mwh": 1000.0,
                        "aviso_ocorrencias": "aviso",
                    },
                    "itens": [
                        {
                            "posicao": 1,
                            "id": RESTRICAO,
                            "texto": "LT 500 kV ACU III / JAGUARUANA II C1",
                            "nome_curto": "LT 500 kV Açu III / Jaguaruana II · C1",
                            "energia_mwh": 1000.0,
                            "fatia_do_total": 1.0,
                            "equipamentos": 1,
                            "subestacoes": ["ACU III", "JAGUARUANA II"],
                            "ocorrencias": 1,
                            "snapshot_id": "2026-09-15",
                        }
                    ],
                },
            )
        if chave == ("GET", f"/restricoes/{RESTRICAO}"):
            return httpx.Response(
                200,
                json={
                    "id": RESTRICAO,
                    "texto": "LT 500 kV ACU III / JAGUARUANA II C1",
                    "nome_curto": "LT 500 kV Açu III / Jaguaruana II · C1",
                    "contingencia": None,
                    "instrucao_operacao": "IO-ON.NE.5NE",
                    "fonte": "eolica",
                    "energia_mwh": 1000.0,
                    "fatia_do_total": 1.0,
                    "subestacoes": ["ACU III", "JAGUARUANA II"],
                    "presente_no_snapshot": True,
                    "snapshot_id": "2026-09-15",
                    "avisos": [],
                    "equipamentos": [
                        {
                            "cod_equipamento": "LT-1",
                            "papel": "contingenciado",
                            "tensao_kv": 500,
                            "subestacao_de": "ACU III",
                            "subestacao_para": "JAGUARUANA II",
                        }
                    ],
                },
            )
        if chave == ("GET", "/simulacoes"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "nome": "Bateria em Açu III",
                        "pergunta": None,
                        "restricao_id": RESTRICAO,
                        "modalidade": "bateria",
                        "revisoes": [
                            {
                                "id": 1,
                                "posicao": 1,
                                "procedencia": "por_pessoa",
                                "revisao_anterior_id": None,
                                "nota": None,
                                "o_que_mudou": "Original, primeira revisão desta simulação.",
                                "vpl_reais": -1e6,
                                "energia_recuperada_mwh": 200.0,
                            }
                        ],
                    }
                ],
            )
        if (
            pedido.method == "GET"
            and caminho.startswith("/simulacoes/")
            and caminho.count("/") == 2
        ):
            revisao_id = int(caminho.rsplit("/", 1)[1])
            irmas = self.irmas()
            posicao = next((i["posicao"] for i in irmas if i["id"] == revisao_id), 2)
            return httpx.Response(
                200,
                json=revisao_completa(
                    revisao_id, posicao=posicao, irmas=irmas, nota=self.anteriores.get(revisao_id)
                ),
            )
        if chave == ("GET", "/simulacoes/1/relatorios"):
            return httpx.Response(200, json=[{"id": 35, "estado": "pronto"}])
        if chave == ("GET", "/simulacoes/1/relatorios/35"):
            return httpx.Response(
                200,
                json={
                    "id": 35,
                    "simulacao_id": 1,
                    "estado": "pronto",
                    "revisoes_cobertas": [1],
                    "revisoes_novas": [],
                    "prosa": {
                        "leitura_geral": "Leitura.",
                        "sensibilidade": "Sensibilidade.",
                        "fora_do_metodo": "Limites.",
                    },
                    "verificacao": {"resultado": "passou"},
                    "derivados": {"fronteiras": {}},
                    "erro": None,
                },
            )
        if chave == ("POST", "/simulacoes/1/relatorios"):
            return httpx.Response(202, json={"id": 35, "simulacao_id": 1, "estado": "gerando"})
        if chave == ("GET", f"/restricoes/{RESTRICAO}/montar"):
            return httpx.Response(
                200,
                json={
                    "restricao_id": RESTRICAO,
                    "snapshot_id": "2026-09-15",
                    "configuracao": CONFIGURACAO,
                    "campos": [
                        {
                            "campo": "bateria.potencia_mw",
                            "valor": 50.0,
                            "origem": "escolha",
                            "premissa_id": None,
                            "fonte": None,
                            "status": None,
                        },
                        {
                            "campo": "financeira.taxa_desconto_aa",
                            "valor": 0.08,
                            "origem": "cenario",
                            "premissa_id": "taxa_desconto",
                            "fonte": "EPE",
                            "status": "proposta",
                        },
                    ],
                    "investimento": [
                        {
                            "intervencao": "bateria",
                            "custo_unitario": {
                                "id": "bateria_capex_kwh",
                                "valor": 1375.0,
                                "unidade": "R$/kWh",
                                "status": "proposta",
                            },
                            "quantidade": 200_000.0,
                            "unidade_da_quantidade": "kWh",
                            "valor_reais": 275_000_000.0,
                            "faixa_reais": [250e6, 450e6],
                            "estimada": True,
                        }
                    ],
                    "avisos": [{"codigo": "custos_de_operacao_zerados", "mensagem": "Zerados."}],
                },
            )
        if chave == ("POST", "/simulacoes"):
            self.proxima_revisao += 1
            return httpx.Response(200, json={"id": self.proxima_revisao, "simulacao_id": 1})
        if chave == ("GET", "/simulacoes/1/exploracao"):
            return httpx.Response(
                200,
                json={
                    "simulacao_id": 1,
                    "revisao_partida_id": 1,
                    "configuracao": CONFIGURACAO,
                    "faixa": FAIXA,
                    "condicoes_fixas": {
                        "cenario": "referencia",
                        "taxa_desconto_aa": 0.08,
                        "preco_energia_reais_mwh": 216.0,
                        "preco_da_premissa": True,
                        "custos_unitarios": [
                            {
                                "id": "bateria_capex_kwh",
                                "valor": 1375.0,
                                "unidade": "R$/kWh",
                                "status": "proposta",
                            }
                        ],
                    },
                    "teto_maximo": 30,
                },
            )
        if chave == ("POST", "/simulacoes/1/tarefas"):
            if self.tarefa_ja_existe:
                return httpx.Response(
                    409,
                    json={"detail": {"mensagem": "já há exploração, a tarefa 4", "tarefa_id": 4}},
                )
            self.tarefa = {
                "id": 7,
                "simulacao_id": 1,
                "estado": "em_andamento",
                "teto": corpo["teto"],
                "pedido": corpo["pedido"],
                "revisao_partida_id": 1,
                "faixa": FAIXA,
                "motivo": None,
                "relatorio_id": None,
            }
            return httpx.Response(201, json=self._tarefa())
        if chave == ("GET", "/tarefas/7"):
            if self.consultas_ate_terminar is not None and self.tarefa is not None:
                self.consultas_ate_terminar -= 1
                if self.consultas_ate_terminar <= 0:
                    self.tarefa["estado"] = "concluida"
            return httpx.Response(200, json=self._tarefa())
        if chave == ("POST", "/tarefas/7/eventos"):
            assert self.tarefa is not None
            self.eventos.append(corpo)
            if corpo["tipo"] == "tarefa_terminada":
                self.tarefa["estado"] = corpo["estado"]
                self.tarefa["motivo"] = corpo["motivo"]
            if corpo["tipo"] == "relatorio_pedido":
                self.tarefa["relatorio_id"] = corpo["relatorio_id"]
            return httpx.Response(201, json={"id": len(self.eventos), "evento": corpo})
        if chave == ("POST", "/simulacoes/1/variacoes"):
            if str(corpo["valor"]) in self.repetidas:
                return httpx.Response(409, json={"detail": "configuração igual à da revisão 3"})
            self.proxima_revisao += 1
            self.criadas.append(self.proxima_revisao)
            self.eventos.append(
                {
                    "tipo": "revisao_pronta",
                    "variacao_id": corpo["variacao_id"],
                    "revisao_id": self.proxima_revisao,
                }
            )
            return httpx.Response(200, json={"id": self.proxima_revisao, "simulacao_id": 1})
        return httpx.Response(404, json={"detail": f"rota falsa não tem {chave}"})


@pytest.fixture
def api_falsa() -> ApiFalsa:
    return ApiFalsa()


async def _explora_nada(tarefa: dict[str, Any]) -> None:
    return None


@pytest.fixture
def contexto(api_falsa: ApiFalsa) -> Contexto:
    """Com um explorador que não faz nada: criar pelo chat exige um. O teste que precisa do
    servidor sem explorador tira este."""
    return Contexto(
        api=ClienteDaApi("http://api", transporte=httpx.MockTransport(api_falsa.responder)),
        config=Configuracao(painel_url="http://painel"),
        iniciar_exploracao=_explora_nada,
    )
