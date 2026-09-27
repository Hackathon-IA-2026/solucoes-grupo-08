"""Aplicação FastAPI do ARCO."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from arco_api.config import configuracao
from arco_api.relatorio import rotas_relatorio
from arco_api.rotas import rotas
from arco_api.tarefas import rotas_tarefas
from arco_ia.chamada import configurar_rastro
from arco_motor import METODO_VERSAO


@asynccontextmanager
async def _ciclo(_: FastAPI) -> AsyncIterator[None]:
    # Rastro das chamadas ao modelo: Langfuse com as chaves, console sem elas (ADR 0013). Na
    # partida e não no import, para o contrato e a suíte não ligarem exportador nenhum.
    configurar_rastro()
    yield


app = FastAPI(
    title="ARCO",
    summary="Análise Retrospectiva do Corte",
    description=(
        "Refaz os cortes de geração renovável registrados pelo ONS com uma intervenção "
        "hipotética e calcula o efeito técnico e financeiro. Uso local, sem autenticação."
    ),
    version="0.1.0",
    lifespan=_ciclo,
)


# Não é camada de segurança: a API é local e sem autenticação. Sem isto o navegador bloqueia a
# interface quando ela chama a API de outra origem, como pelo túnel de `make tunel`.
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracao().origens(),
    allow_methods=["*"],
    allow_headers=["*"],
)


class Saude(BaseModel):
    status: str
    metodo_versao: str


app.include_router(rotas)
app.include_router(rotas_relatorio)
app.include_router(rotas_tarefas)


@app.get("/saude", tags=["sistema"], operation_id="saude")
def saude() -> Saude:
    """Diz se a API está de pé e qual versão do método de cálculo está em vigor."""
    return Saude(status="ok", metodo_versao=METODO_VERSAO)
