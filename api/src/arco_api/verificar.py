"""Confere o que `make servidor` precisa do projeto: banco, esquema, snapshot, chave e portas.

Roda antes de subir qualquer coisa, chamado por `infra/verificar.sh`, que confere antes as
ferramentas da máquina. Usa a mesma configuração da API, para a conferência não ter uma segunda
regra que um dia diverge da primeira. Cada item diz o que está ok e, quando falta, como resolver.

`python -m arco_api.verificar [--porta-api 8000] [--porta-mcp 8100]`. Sai 1 se faltar algum item.
"""

from __future__ import annotations

import argparse
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from arco_api.config import configuracao
from arco_api.modelos import Snapshot
from arco_ia.config import VARIAVEL_DA_CHAVE, chave

ALEMBIC = Path(__file__).resolve().parents[2] / "alembic.ini"


@dataclass(frozen=True)
class Item:
    ok: bool
    texto: str
    dica: str = ""


def _onde(url: str) -> str:
    """Host, porta e banco, sem usuário nem senha: a linha vai para o terminal."""
    endereco = make_url(url)
    if endereco.get_backend_name() == "sqlite":
        return endereco.database or "memória"
    return f"{endereco.host or 'localhost'}:{endereco.port or 5432}/{endereco.database}"


def _cabecas() -> set[str]:
    configuracao_alembic = Config(str(ALEMBIC))
    # O `script_location` do .ini é relativo a `api/`, de onde `make migrar` roda o Alembic.
    configuracao_alembic.set_main_option("script_location", str(ALEMBIC.parent / "alembic"))
    return set(ScriptDirectory.from_config(configuracao_alembic).get_heads())


def _esquema_e_snapshot(conexao: Connection) -> list[Item]:
    atual = set(MigrationContext.configure(conexao).get_current_heads())
    cabecas = _cabecas()
    if not atual:
        return [
            Item(False, "Banco sem esquema", "make migrar (ou make banco, que também carrega)"),
            Item(False, "Nenhum snapshot carregado", "make snapshot e depois make banco"),
        ]
    if atual != cabecas:
        return [
            Item(
                False,
                f"Esquema desatualizado: {', '.join(sorted(atual))}, "
                f"a última é {', '.join(sorted(cabecas))}",
                "make migrar",
            )
        ]
    esquema = Item(True, f"Esquema na última versão ({', '.join(sorted(cabecas))})")
    ativo = conexao.scalar(select(Snapshot.id).where(Snapshot.ativo.is_(True)))
    if ativo is None:
        return [
            esquema,
            Item(False, "Nenhum snapshot carregado", "make snapshot e depois make banco"),
        ]
    return [esquema, Item(True, f"Snapshot {ativo} carregado")]


def conferir_banco(url: str) -> list[Item]:
    """O banco responde, o esquema está na última migration e há snapshot ativo."""
    onde = _onde(url)
    backend = make_url(url).get_backend_name()
    # Sem prazo, um host que não responde seguraria a conferência por minutos.
    extras = {"connect_timeout": 3} if backend == "postgresql" else {}
    motor = create_engine(url, connect_args=extras)
    try:
        try:
            conexao = motor.connect()
        except SQLAlchemyError as erro:
            motivo, dica = _por_que(str(getattr(erro, "orig", None) or erro))
            return [Item(False, f"Banco inacessível em {onde}: {motivo}", dica)]
        with conexao:
            return [Item(True, f"Banco em {onde}"), *_esquema_e_snapshot(conexao)]
    finally:
        motor.dispose()


SUBIR_O_BANCO = "suba o Postgres com make db (na primeira vez, make bootstrap)"
HOST_E_PORTA = "confira o host e a porta em DATABASE_URL no .env"
_MOTIVOS = (
    (
        "authentication failed",
        "usuário ou senha recusados",
        "confira DATABASE_URL no .env; se outro Postgres usa essa porta, troque ARCO_PG_PORTA "
        "e a porta de DATABASE_URL pelo mesmo número",
    ),
    (
        "does not exist",
        "o banco ou o usuário não existe",
        "confira DATABASE_URL no .env; o Postgres do projeto sobe com make db",
    ),
    ("connection refused", "ninguém atende nessa porta", SUBIR_O_BANCO),
    # O psycopg dá tempo esgotado também quando ninguém atende em localhost, que é o banco parado.
    ("timeout", "ninguém respondeu em 3 s", f"{SUBIR_O_BANCO}; se já está no ar, {HOST_E_PORTA}"),
    ("timed out", "ninguém respondeu em 3 s", f"{SUBIR_O_BANCO}; se já está no ar, {HOST_E_PORTA}"),
)


def _por_que(erro: str) -> tuple[str, str]:
    """O motivo em poucas palavras e a dica que resolve. A mensagem do driver é longa e em
    inglês, e a mesma dica para senha errada e banco parado mandaria a pessoa ao lugar errado."""
    minusculo = erro.lower()
    for trecho, motivo, dica in _MOTIVOS:
        if trecho in minusculo:
            return motivo, dica
    return erro.strip().splitlines()[0][:120], SUBIR_O_BANCO


def conferir_chave(achada: str) -> Item:
    if achada:
        return Item(True, VARIAVEL_DA_CHAVE)
    return Item(
        False,
        f"{VARIAVEL_DA_CHAVE} ausente: sem ela a exploração por agente e o relatório não rodam",
        "gere a chave no Google AI Studio e ponha no .env (ver .env.exemplo)",
    )


def conferir_porta(porta: int, quem: str, como_trocar: str) -> Item:
    """Livre é ninguém atendendo em localhost. Ocupada, o processo morreria ao subir."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
        teste.settimeout(1)
        ocupada = teste.connect_ex(("127.0.0.1", porta)) == 0
    if not ocupada:
        return Item(True, f"Porta {porta} livre para {quem}")
    return Item(
        False,
        f"Porta {porta} ocupada, e {quem} não sobe nela",
        f"se for o ARCO já no ar, Ctrl+C no terminal dele; senão, {como_trocar}",
    )


def conferir(url: str, chave_em_uso: str, porta_api: int, porta_mcp: int) -> list[Item]:
    return [
        *conferir_banco(url),
        conferir_chave(chave_em_uso),
        conferir_porta(porta_api, "a API", "outra porta: make servidor PORTA=8001"),
        conferir_porta(porta_mcp, "o MCP", "outra porta em ARCO_MCP_PORTA no .env"),
    ]


def imprimir(itens: list[Item]) -> None:
    for item in itens:
        print(f"  {'ok' if item.ok else 'falta':<6} {item.texto}")
        if not item.ok and item.dica:
            print(f"         → {item.dica}")


def main(argv: list[str] | None = None) -> int:
    argumentos = argparse.ArgumentParser(description="Confere o que make servidor precisa.")
    argumentos.add_argument("--porta-api", type=int, default=8000)
    argumentos.add_argument("--porta-mcp", type=int, default=8100)
    lidos = argumentos.parse_args(argv)
    itens = conferir(configuracao().database_url, chave(), lidos.porta_api, lidos.porta_mcp)
    imprimir(itens)
    return 0 if all(item.ok for item in itens) else 1


if __name__ == "__main__":
    sys.exit(main())
