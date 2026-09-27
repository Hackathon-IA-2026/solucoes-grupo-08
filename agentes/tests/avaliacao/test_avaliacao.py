"""Conjunto de avaliação do explorador (feature 17, task 17.16): o agente se justifica?

Cada caso é um pedido com resposta conhecida sobre uma série sintética. O explorador com o
modelo e a árvore de referência (regra 6) rodam com o mesmo teto, cada um numa simulação nova,
contra a API de verdade com Postgres; por caso e por decisor, a avaliação registra se a
exploração achou a fronteira, a largura do intervalo em que a deixou, as revisões usadas, as
recusas, as rodadas, os tokens e o tempo.

**A resposta conhecida sai do motor**, sobre a mesma série que a API calcula e com a variação
montada pela mesma função que a rota usa (`montar_variacao`): a fronteira é procurada por
bisseção, até 1 MW. "Achou" quer dizer que, entre as revisões da exploração, há duas vizinhas na
ordem da alavanca, uma de cada lado da condição, com a fronteira entre elas.

A série é inventada: um ano de cortes noturnos, das 20h às 5h, de 60 a 260 MW. Custos, preço e
premissas são os do catálogo, no cenário de referência. Nada aqui é dado do ONS.

`agentes` não importa `arco_api`: a avaliação prepara o banco e sobe a API por subprocesso, como
qualquer pessoa faria, e fala com ela por HTTP.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import math
import os
import subprocess
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from arco_agentes.api import ClienteDaApi
from arco_agentes.config import CAMINHO_DO_EXPLORADOR, Configuracao
from arco_agentes.explorador import DecisorDoModelo, explorar_com
from arco_agentes.referencia import ArvoreDeReferencia
from arco_agentes.servidor import Contexto, em_segundo_plano
from arco_motor.premissas import PREMISSAS_PADRAO
from arco_motor.simular import simular
from arco_motor.tipos import Configuracao as ConfiguracaoDoMotor
from arco_motor.tipos import Intervalo, SerieRestricao
from arco_motor.variacao import AlavancaFisica, FaixaPermitida, Limites, Variacao, montar_variacao

RAIZ = Path(__file__).resolve().parents[3]
INICIO, FIM = datetime(2025, 9, 1), datetime(2026, 9, 1)
SNAPSHOT = "sintetico-avaliacao"
RESTRICAO = "sintetica001"
LINHA = "LT-SINTETICA-1"
TETO = 12
"""O mesmo teto para os dois decisores: a comparação é com o mesmo gasto de cálculo."""

RECUSA_PROIBIDA = ("fora da faixa", "não varia", "preço", "taxa", "cenário")
"""Recusa que não pode aparecer: condição fixa ou faixa. Repetida, pode."""


def serie() -> list[tuple[datetime, float]]:
    """Um ano de cortes das 20h às 5h, com amplitude que varia por estação e de dia para dia."""
    pontos = []
    instante = INICIO
    while instante < FIM:
        if instante.hour >= 20 or instante.hour < 5:
            dia = (instante - INICIO).days
            corte = 160 + 70 * math.sin(2 * math.pi * dia / 365) + 30 * math.sin(dia)
            pontos.append((instante, round(corte, 1)))
        instante += timedelta(minutes=30)
    return pontos


def serie_do_motor() -> SerieRestricao:
    return SerieRestricao(
        restricao_id=RESTRICAO,
        snapshot_id=SNAPSHOT,
        intervalos=[Intervalo(instante=i, corte_mw=mw, minutos_cnf=30) for i, mw in serie()],
        periodo_inicio=INICIO,
        periodo_fim=FIM,
    )


@dataclass(frozen=True)
class Caso:
    nome: str
    pedido: str
    montar: dict[str, Any]
    alavanca: AlavancaFisica
    atinge: Callable[[dict[str, Any]], bool]
    """A condição do pedido sobre o resultado de uma revisão."""
    sobe: bool
    """Verdadeiro se a condição passa a valer com a alavanca maior; falso se deixa de valer."""


BATERIA_50_MW = {
    "modalidade": "bateria",
    "potencia_mw": 50,
    "capacidade_mwh": 200,
    "subestacao": "ACU III",
}

CASOS = [
    Caso(
        nome="fracao_50",
        pedido="Com que potência, mantendo 4 horas de duração, a bateria recupera metade do corte?",
        montar=BATERIA_50_MW,
        alavanca=AlavancaFisica.POTENCIA,
        atinge=lambda r: r["fracao_recuperada"] >= 0.5,
        sobe=True,
    ),
    Caso(
        nome="payback_20",
        pedido="Até que potência, mantendo 4 horas de duração, o payback simples da bateria "
        "cabe em 20 anos?",
        montar=BATERIA_50_MW,
        alavanca=AlavancaFisica.POTENCIA,
        atinge=lambda r: r["payback_simples_anos"] is not None and r["payback_simples_anos"] <= 20,
        sobe=False,
    ),
    Caso(
        nome="ganho_50",
        pedido="Que ganho de limite do circuito novo recupera metade do corte?",
        montar={"modalidade": "equipamento", "cod_equipamento": LINHA, "ganho_limite_mw": 20},
        alavanca=AlavancaFisica.GANHO,
        atinge=lambda r: r["fracao_recuperada"] >= 0.5,
        sobe=True,
    ),
]


# Ambiente: banco, carga, API e MCP --------------------------------------------------------


@dataclass
class Ambiente:
    api_url: str
    mcp_url: str


def _psycopg(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _zerar(url: str) -> None:
    import psycopg

    with psycopg.connect(_psycopg(url), autocommit=True) as conexao:
        conexao.execute("DROP SCHEMA public CASCADE")
        conexao.execute("CREATE SCHEMA public")


def _rodar(comando: list[str], url: str) -> None:
    subprocess.run(comando, cwd=RAIZ, env=os.environ | {"DATABASE_URL": url}, check=True)


def _artefatos(pasta: Path) -> Path:
    """No formato que o preparo da feature 02 emite, com uma restrição, uma linha e o vínculo
    casado: a carga o autoriza sozinha."""
    import duckdb

    pasta.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE serie (restricao_id VARCHAR, fonte VARCHAR, instante TIMESTAMP, "
        "corte_mw DOUBLE, minutos_cnf INTEGER, snapshot_id VARCHAR)"
    )
    con.executemany(
        "INSERT INTO serie VALUES (?, 'eolica', ?, ?, 30, ?)",
        [(RESTRICAO, i, mw, SNAPSHOT) for i, mw in serie()],
    )
    con.execute(f"COPY serie TO '{pasta / 'serie.parquet'}' (FORMAT PARQUET)")
    energia = sum(mw * 0.5 for _, mw in serie())
    capacidades = ", ".join(
        f"{v} AS {c}"
        for c, v in [
            ("val_capacoperlongasemlimit", 3005.0),
            ("val_capacoperlongacomlimit", 3005.0),
            ("val_capacopercurtasemlimit", 4000.0),
            ("val_capacopercurtacomlimit", 4000.0),
        ]
    )
    comandos = {
        "restricoes": f"SELECT '{RESTRICAO}' AS restricao_id, 'CONTROLE DE CARREGAMENTO DA LT "
        "500 KV ACU III / SINTETICA II C1 (SERIE SINTETICA DE AVALIACAO)' AS texto, 'LOC' AS "
        "origem, 'CNF' AS razao, 'LT 500 kV Açu III / Sintética II · C1' AS nome_curto, NULL "
        f"AS contingencia, NULL AS instrucao_operacao, {energia} AS energia_mwh, "
        f"{len(serie())} AS registros, '{SNAPSHOT}' AS snapshot_id, TIMESTAMP '{INICIO}' AS "
        f"periodo_inicio, TIMESTAMP '{FIM}' AS periodo_fim",
        "equipamentos": f"SELECT '{LINHA}' AS cod_equipamento, 500 AS tensao_kv, 'ACU III' AS "
        "subestacao_de, 'SINTETICA II' AS subestacao_para, 1 AS num_barra_de, 2 AS "
        "num_barra_para, 'LT 500 kV ACU III / SINTETICA II C1' AS nome, 'SINTETICO' AS "
        f"proprietario, 150.0 AS comprimento_km, {capacidades}, NULL::DOUBLE AS "
        "val_capacidadeoperveraodialonga, NULL::DOUBLE AS val_capacidadeoperveraonoitelonga, "
        "NULL::DOUBLE AS val_capacoperinvernodialonga, NULL::DOUBLE AS "
        "val_capacoperinvernonoitelonga, NULL::DOUBLE AS val_capacoperveradiacurta, "
        "NULL::DOUBLE AS val_capacoperveraonoitecurta, NULL::DOUBLE AS "
        "val_capacoperinvernodiacurta, NULL::DOUBLE AS val_capacoperinvernonoitecurta, "
        f"'{SNAPSHOT}' AS snapshot_id",
        "subestacoes": "SELECT * FROM (VALUES ('ACU III', -5.5, -36.9, 1, 500.0, "
        f"'{SNAPSHOT}'), ('SINTETICA II', -5.0, -37.0, 2, 500.0, '{SNAPSHOT}')) AS t(nome, "
        "val_latitude, val_longitude, num_barra, val_niveltensao, snapshot_id)",
        "propostas_vinculo": f"SELECT '{RESTRICAO}' AS restricao_id, '{LINHA}' AS "
        "cod_equipamento, NULL AS candidatos, 'monitorado' AS papel, FALSE AS alternativo, "
        "'casado' AS situacao, '500 KV ACU III / SINTETICA II C1' AS citacao, 'proposto' AS "
        f"status, 'parser' AS origem, '{SNAPSHOT}' AS snapshot_id",
    }
    for nome, consulta in comandos.items():
        con.execute(f"COPY ({consulta}) TO '{pasta / f'{nome}.parquet'}' (FORMAT PARQUET)")
    return pasta


def _porta_livre() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Ambiente]:
    from arco_ia.config import VARIAVEL_DA_CHAVE, chave

    if not chave():
        pytest.skip(f"sem {VARIAVEL_DA_CHAVE}")
    url = os.environ.get("ARCO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("sem ARCO_TEST_DATABASE_URL, o Postgres descartável que a avaliação zera")
    _zerar(url)
    _rodar(["uv", "run", "--directory", "api", "alembic", "upgrade", "head"], url)
    artefatos = _artefatos(tmp_path_factory.mktemp("artefatos") / SNAPSHOT)
    _rodar(
        [
            "uv",
            "run",
            "python",
            "-m",
            "arco_api.comandos",
            "carregar",
            "--artefatos",
            str(artefatos),
        ],
        url,
    )
    porta = _porta_livre()
    api = subprocess.Popen(
        ["uv", "run", "uvicorn", "arco_api.main:app", "--port", str(porta)],
        cwd=RAIZ,
        env=os.environ | {"DATABASE_URL": url},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    api_url = f"http://127.0.0.1:{porta}"
    try:
        for _ in range(240):
            try:
                if httpx.get(f"{api_url}/saude", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        contexto = Contexto(api=ClienteDaApi(api_url), config=Configuracao(api_url=api_url))
        with em_segundo_plano(contexto) as mcp:
            yield Ambiente(api_url=api_url, mcp_url=f"{mcp}{CAMINHO_DO_EXPLORADOR}")
    finally:
        api.terminate()
        api.wait(timeout=30)


# A resposta conhecida --------------------------------------------------------------------


def _valor(configuracao: dict[str, Any], alavanca: AlavancaFisica) -> float:
    if alavanca is AlavancaFisica.GANHO:
        return float(configuracao["equipamento"]["ganho_limite_mw"])
    return float(configuracao["bateria"]["potencia_mw"])


def fronteira(caso: Caso, partida: dict[str, Any]) -> float:
    """Por bisseção no motor, até 1 MW: o menor valor em que a condição passa a valer, se ela
    sobe com a alavanca, ou o maior em que ainda vale, se desce."""
    config = ConfiguracaoDoMotor.model_validate(partida)
    base = _valor(partida, caso.alavanca)
    ampla = FaixaPermitida(
        potencia_mw=Limites(minimo=0, maximo=1e9),
        duracao_horas=Limites(minimo=0, maximo=1e9),
        ganho_limite_mw=Limites(minimo=0, maximo=1e9),
    )
    serie_motor = serie_do_motor()

    def atinge(valor: float) -> bool:
        variada = montar_variacao(
            config, Variacao(alavanca=caso.alavanca, valor=valor), PREMISSAS_PADRAO, ampla
        ).configuracao
        resultado = simular(serie_motor, variada, PREMISSAS_PADRAO)
        return caso.atinge(
            {
                "fracao_recuperada": resultado.tecnico.fracao_recuperada,
                "payback_simples_anos": resultado.financeiro.payback_simples_anos,
            }
        )

    baixo, alto = base * 0.5, base * 8 if caso.alavanca is AlavancaFisica.POTENCIA else 3005.0
    assert atinge(baixo) != caso.sobe and atinge(alto) == caso.sobe, "caso mal desenhado"
    while alto - baixo > 1:
        meio = (baixo + alto) / 2
        if atinge(meio) == caso.sobe:
            alto = meio
        else:
            baixo = meio
    return alto if caso.sobe else baixo


# A execução ------------------------------------------------------------------------------


def _explorar(ambiente: Ambiente, caso: Caso, decisor_nome: str) -> dict[str, Any]:
    async def rodar() -> dict[str, Any]:
        api = ClienteDaApi(ambiente.api_url)
        try:
            montada = await api.montar(RESTRICAO, dict(caso.montar))
            salva = await api.salvar(
                {
                    "restricao_id": RESTRICAO,
                    "nome": f"Avaliação {caso.nome} ({decisor_nome})",
                    "configuracao": montada["configuracao"],
                }
            )
            # O conjunto roda o próprio decisor: a API não dispara o do processo de `agentes`.
            tarefa = await api.criar_tarefa(
                salva["simulacao_id"], {"pedido": caso.pedido, "teto": TETO, "disparar": False}
            )
            decisor = DecisorDoModelo() if decisor_nome == "modelo" else ArvoreDeReferencia()
            inicio = time.monotonic()
            exploracao = await explorar_com(
                ambiente.api_url, ambiente.mcp_url, tarefa["id"], decisor
            )
            tempo = time.monotonic() - inicio
            fim = await api.ver_tarefa(tarefa["id"])
            partida = await api.ver_revisao(salva["id"])
            revisoes = [await api.ver_revisao(r["id"]) for r in partida["revisoes"]]
            return {
                "partida": montada["configuracao"],
                "tarefa": fim,
                "exploracao": exploracao,
                "revisoes": revisoes,
                "recusas": await _recusas(ambiente.api_url, tarefa["id"]),
                "tempo_s": tempo,
                "tokens": sum(
                    c["tokens_entrada"] + c["tokens_saida"]
                    for c in getattr(decisor, "chamadas", [])
                ),
            }
        finally:
            await api.fechar()

    return asyncio.run(rodar())


async def _recusas(api_url: str, tarefa_id: int) -> list[str]:
    """Os motivos de recusa, lidos da trilha. A tarefa terminou, então o streaming fecha."""
    async with httpx.AsyncClient(timeout=60) as http:
        corpo = (await http.get(f"{api_url}/tarefas/{tarefa_id}/eventos")).text
    eventos = [
        json.loads(linha.removeprefix("data: "))["evento"]
        for linha in corpo.splitlines()
        if linha.startswith("data: ")
    ]
    return [e["motivo"] for e in eventos if e["tipo"] == "variacao_recusada"]


def _intervalo(
    caso: Caso, partida: dict[str, Any], revisoes: list[dict[str, Any]], alvo: float
) -> tuple[float, float] | None:
    """As duas revisões vizinhas, na ordem da alavanca, que cercam a fronteira. Só entram as que
    diferem da partida na alavanca do caso: na bateria, a mesma duração e a mesma subestação."""
    pontos: dict[float, bool] = {}
    for revisao in revisoes:
        config = revisao["configuracao"]
        if caso.alavanca is AlavancaFisica.POTENCIA:
            bateria, base = config.get("bateria"), partida["bateria"]
            if not bateria or bateria["subestacao"] != base["subestacao"]:
                continue
            if not math.isclose(
                bateria["capacidade_mwh"] / bateria["potencia_mw"],
                base["capacidade_mwh"] / base["potencia_mw"],
            ):
                continue
        elif not config.get("equipamento"):
            continue
        fin, tec = revisao["resultado"]["financeiro"], revisao["resultado"]["tecnico"]
        numeros = {
            "fracao_recuperada": tec["fracao_recuperada"],
            "payback_simples_anos": fin["payback_simples_anos"],
        }
        pontos[_valor(config, caso.alavanca)] = caso.atinge(numeros)
    ordem = sorted(pontos)
    for antes, depois in itertools.pairwise(ordem):
        if pontos[antes] != pontos[depois] and antes <= alvo <= depois:
            return antes, depois
    return None


@pytest.mark.lento
@pytest.mark.parametrize("decisor", ["modelo", "referencia"])
@pytest.mark.parametrize("caso", CASOS, ids=[c.nome for c in CASOS])
def test_explorador_contra_a_referencia(
    ambiente: Ambiente, caso: Caso, decisor: str, registrar: Any
) -> None:
    feito = _explorar(ambiente, caso, decisor)
    alvo = fronteira(caso, feito["partida"])
    intervalo = _intervalo(caso, feito["partida"], feito["revisoes"], alvo)
    contagem = feito["tarefa"]["contagem"]
    registrar(
        {
            "caso": caso.nome,
            "decisor": decisor,
            "fronteira": alvo,
            "achou": intervalo is not None,
            "antes": intervalo[0] if intervalo else None,
            "depois": intervalo[1] if intervalo else None,
            "largura": round(intervalo[1] - intervalo[0], 1) if intervalo else None,
            "revisoes": contagem["prontas"],
            "recusas": contagem["recusadas"],
            "rodadas": contagem["rodadas"],
            "tokens": feito["tokens"],
            "tempo_s": feito["tempo_s"],
            "estado": feito["tarefa"]["estado"],
            "fim": feito["exploracao"].fim,
            "decisoes": feito["exploracao"].decisoes,
            "motivos_de_recusa": feito["recusas"],
        }
    )

    assert feito["tarefa"]["estado"] == "concluida", feito["exploracao"].erro
    proibidas = [m for m in feito["recusas"] if any(p in m for p in RECUSA_PROIBIDA)]
    assert proibidas == [], "recusa por condição fixa ou faixa"
