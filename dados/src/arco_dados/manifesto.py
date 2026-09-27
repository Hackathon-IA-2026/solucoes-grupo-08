"""Manifesto de um snapshot: o que foi copiado, de onde, com que hash."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from arco_dados.fontes import BASE_URL, LICENCA


class ArquivoManifesto(BaseModel):
    chave: str
    arquivo: str
    fonte: str
    tamanho: int
    etag: str
    modificado_em: datetime
    sha256: str


class Manifesto(BaseModel):
    versao: int = 1
    gerado_em: datetime
    base_url: str = BASE_URL
    licenca: str = LICENCA
    arquivos: list[ArquivoManifesto] = Field(default_factory=list)

    def por_chave(self) -> dict[str, ArquivoManifesto]:
        return {a.chave: a for a in self.arquivos}

    @property
    def tamanho_total(self) -> int:
        return sum(a.tamanho for a in self.arquivos)


class Diferencas(BaseModel):
    novos: list[str] = Field(default_factory=list)
    removidos: list[str] = Field(default_factory=list)
    alterados: list[str] = Field(default_factory=list)

    @property
    def iguais(self) -> bool:
        return not (self.novos or self.removidos or self.alterados)


def comparar(anterior: Manifesto, novo: Manifesto) -> Diferencas:
    """Compara pelo sha256 do conteúdo, não pelo ETag nem pela data."""
    a, b = anterior.por_chave(), novo.por_chave()
    return Diferencas(
        novos=sorted(set(b) - set(a)),
        removidos=sorted(set(a) - set(b)),
        alterados=sorted(chave for chave in set(a) & set(b) if a[chave].sha256 != b[chave].sha256),
    )


def sha256_de(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def carregar(caminho: Path) -> Manifesto:
    return Manifesto.model_validate_json(caminho.read_text(encoding="utf-8"))


def salvar(manifesto: Manifesto, caminho: Path) -> None:
    caminho.write_text(manifesto.model_dump_json(indent=2) + "\n", encoding="utf-8")


def escrever_notas(manifesto: Manifesto, caminho: Path) -> None:
    """NOTAS.md da release: resumo legível do snapshot."""
    linhas = [
        f"# Snapshot dos dados abertos do ONS, {manifesto.gerado_em:%Y-%m-%d %H:%M} UTC",
        "",
        f"{len(manifesto.arquivos)} arquivos, {manifesto.tamanho_total / 1e6:.1f} MB. "
        f"Fonte: `{manifesto.base_url}/dataset/`. Licença: {manifesto.licenca}",
        "",
        "O `manifesto.json` traz, por arquivo, a chave no bucket, o tamanho, o ETag, a data de "
        "modificação no bucket e o sha256 do conteúdo copiado.",
        "",
        "| fonte | arquivo | MB | modificado no bucket | sha256 |",
        "|---|---|---|---|---|",
    ]
    for a in manifesto.arquivos:
        linhas.append(
            f"| {a.fonte} | {a.arquivo} | {a.tamanho / 1e6:.2f} "
            f"| {a.modificado_em:%Y-%m-%d %H:%M} | `{a.sha256[:12]}` |"
        )
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
