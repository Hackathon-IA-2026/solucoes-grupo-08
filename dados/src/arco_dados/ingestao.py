"""Ingestão: copia os arquivos do bucket do ONS para uma pasta e escreve o manifesto.

É o único módulo que fala com o ONS. Nada aqui é lido por código de cálculo.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from arco_dados.fontes import BASE_URL, FONTES, listar, nome_local, selecionar
from arco_dados.manifesto import (
    ArquivoManifesto,
    Manifesto,
    escrever_notas,
    salvar,
    sha256_de,
)


def baixar_arquivo(cliente: httpx.Client, url: str, alvo: Path) -> str:
    """Baixa em streaming para um temporário, renomeia no fim e devolve o sha256."""
    temporario = alvo.with_suffix(alvo.suffix + ".parcial")
    with cliente.stream("GET", url) as resposta:
        resposta.raise_for_status()
        with temporario.open("wb") as saida:
            for bloco in resposta.iter_bytes(1 << 20):
                saida.write(bloco)
    temporario.replace(alvo)
    return sha256_de(alvo)


def ingerir(
    destino: Path,
    incluir_opcionais: bool = False,
    cliente: httpx.Client | None = None,
    agora: datetime | None = None,
    informar: Callable[[str], None] | None = None,
) -> Manifesto:
    """Copia todas as fontes para `destino` e grava `manifesto.json` e `NOTAS.md`."""
    destino.mkdir(parents=True, exist_ok=True)
    cli = cliente or httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0), follow_redirects=True)
    avisar = informar or (lambda _: None)
    arquivos: list[ArquivoManifesto] = []
    try:
        for fonte in FONTES:
            if not fonte.obrigatoria and not incluir_opcionais:
                continue
            objetos = selecionar(fonte, listar(fonte.pasta, cli))
            if fonte.obrigatoria and not objetos:
                raise RuntimeError(f"fonte {fonte.nome}: nenhum arquivo em {fonte.pasta}")
            for objeto in objetos:
                alvo = destino / nome_local(objeto.chave)
                avisar(f"{fonte.nome}: {objeto.nome} ({objeto.tamanho / 1e6:.1f} MB)")
                sha = baixar_arquivo(cli, f"{BASE_URL}/{objeto.chave}", alvo)
                arquivos.append(
                    ArquivoManifesto(
                        chave=objeto.chave,
                        arquivo=alvo.name,
                        fonte=fonte.nome,
                        tamanho=objeto.tamanho,
                        etag=objeto.etag,
                        modificado_em=objeto.modificado_em,
                        sha256=sha,
                    )
                )
    finally:
        if cliente is None:
            cli.close()
    manifesto = Manifesto(
        gerado_em=agora or datetime.now(UTC), arquivos=sorted(arquivos, key=lambda a: a.chave)
    )
    salvar(manifesto, destino / "manifesto.json")
    escrever_notas(manifesto, destino / "NOTAS.md")
    return manifesto
