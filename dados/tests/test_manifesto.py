from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from arco_dados.manifesto import (
    ArquivoManifesto,
    Manifesto,
    carregar,
    comparar,
    escrever_notas,
    salvar,
    sha256_de,
)


def arquivo(chave: str, sha: str) -> ArquivoManifesto:
    return ArquivoManifesto(
        chave=chave,
        arquivo=chave.replace("/", "__"),
        fonte="teste",
        tamanho=1,
        etag="e",
        modificado_em=datetime(2026, 9, 15, tzinfo=UTC),
        sha256=sha,
    )


def test_comparar_detecta_novo_removido_e_alterado() -> None:
    antes = Manifesto(
        gerado_em=datetime(2026, 9, 14, tzinfo=UTC), arquivos=[arquivo("a", "1"), arquivo("b", "1")]
    )
    depois = Manifesto(
        gerado_em=datetime(2026, 9, 15, tzinfo=UTC), arquivos=[arquivo("a", "2"), arquivo("c", "1")]
    )
    d = comparar(antes, depois)
    assert (d.novos, d.removidos, d.alterados) == (["c"], ["b"], ["a"])
    assert not d.iguais


def test_comparar_ignora_data_e_etag() -> None:
    a = arquivo("a", "1")
    b = a.model_copy(update={"etag": "outro", "modificado_em": datetime(2026, 9, 16, tzinfo=UTC)})
    assert comparar(
        Manifesto(gerado_em=datetime(2026, 9, 14, tzinfo=UTC), arquivos=[a]),
        Manifesto(gerado_em=datetime(2026, 9, 15, tzinfo=UTC), arquivos=[b]),
    ).iguais


def test_salvar_carregar_e_notas(tmp_path: Path) -> None:
    m = Manifesto(
        gerado_em=datetime(2026, 9, 15, tzinfo=UTC),
        arquivos=[arquivo("dataset/x/y.parquet", "abc")],
    )
    salvar(m, tmp_path / "manifesto.json")
    assert carregar(tmp_path / "manifesto.json") == m
    escrever_notas(m, tmp_path / "NOTAS.md")
    notas = (tmp_path / "NOTAS.md").read_text(encoding="utf-8")
    assert "CC-BY" in notas and "y.parquet" in notas


def test_sha256_de_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "a.bin"
    caminho.write_bytes(b"arco")
    assert sha256_de(caminho) == hashlib.sha256(b"arco").hexdigest()
