"""Descarga de snapshots publicados como releases do GitHub, com conferência de hash."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx

from arco_dados.config import repositorio_de_snapshots, token_do_github
from arco_dados.manifesto import carregar, sha256_de

API = "https://api.github.com"
REPO_PADRAO = "Hackathon-IA-2026/solucoes-grupo-08"
PREFIXO_TAG = "snapshot/"


def _cabecalhos(token: str | None, aceitar: str = "application/vnd.github+json") -> dict[str, str]:
    cabecalhos = {"Accept": aceitar, "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    return cabecalhos


def resolver_release(cliente: httpx.Client, repo: str, tag: str, token: str | None) -> dict:
    """Devolve o JSON da release: a mais recente com prefixo `snapshot/` quando tag é `latest`."""
    if tag != "latest":
        resposta = cliente.get(
            f"{API}/repos/{repo}/releases/tags/{tag}", headers=_cabecalhos(token)
        )
        resposta.raise_for_status()
        return resposta.json()
    resposta = cliente.get(
        f"{API}/repos/{repo}/releases", headers=_cabecalhos(token), params={"per_page": 100}
    )
    resposta.raise_for_status()
    candidatas = [
        r for r in resposta.json() if not r.get("draft") and r["tag_name"].startswith(PREFIXO_TAG)
    ]
    if not candidatas:
        raise RuntimeError(f"nenhuma release {PREFIXO_TAG}* em {repo}")
    return max(candidatas, key=lambda r: r["created_at"])


def baixar_release(
    tag: str = "latest",
    destino: Path = Path("dados/snapshots"),
    repo: str | None = None,
    token: str | None = None,
    cliente: httpx.Client | None = None,
    informar: Callable[[str], None] | None = None,
) -> Path:
    """Baixa os assets da release para `destino/<data>` e confere cada sha256 pelo manifesto."""
    repo = repo or repositorio_de_snapshots() or REPO_PADRAO
    token = token or token_do_github() or None
    avisar = informar or (lambda _: None)
    cli = cliente or httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0), follow_redirects=True)
    try:
        release = resolver_release(cli, repo, tag, token)
        nome = release["tag_name"].removeprefix(PREFIXO_TAG)
        pasta = destino / nome
        pasta.mkdir(parents=True, exist_ok=True)
        assets = {a["name"]: a for a in release["assets"]}
        if "manifesto.json" not in assets:
            raise RuntimeError(f"release {release['tag_name']} sem manifesto.json")
        _baixar_asset(cli, assets["manifesto.json"], pasta / "manifesto.json", token)
        manifesto = carregar(pasta / "manifesto.json")
        for arquivo in manifesto.arquivos:
            alvo = pasta / arquivo.arquivo
            if alvo.exists() and sha256_de(alvo) == arquivo.sha256:
                continue
            avisar(f"{arquivo.arquivo} ({arquivo.tamanho / 1e6:.1f} MB)")
            _baixar_asset(cli, assets[arquivo.arquivo], alvo, token)
            if sha256_de(alvo) != arquivo.sha256:
                raise RuntimeError(f"hash diferente do manifesto: {arquivo.arquivo}")
        (destino / "ultimo.txt").write_text(nome + "\n", encoding="utf-8")
        return pasta
    finally:
        if cliente is None:
            cli.close()


def _baixar_asset(cliente: httpx.Client, asset: dict, alvo: Path, token: str | None) -> None:
    temporario = alvo.with_suffix(alvo.suffix + ".parcial")
    with cliente.stream(
        "GET", asset["url"], headers=_cabecalhos(token, "application/octet-stream")
    ) as resposta:
        resposta.raise_for_status()
        with temporario.open("wb") as saida:
            for bloco in resposta.iter_bytes(1 << 20):
                saida.write(bloco)
    temporario.replace(alvo)
