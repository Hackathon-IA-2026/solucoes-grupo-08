"""CLI `arco-dados`: ingerir, comparar, baixar, preparar.

A carga no Postgres não mora aqui: este pacote não abre conexão com banco. Ver ADR 0005.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from arco_dados import ingestao, manifesto, releases
from arco_dados import preparar as _preparar
from arco_dados.config import token_do_github

app = typer.Typer(
    help="Dados do ARCO: ingestão do ONS, snapshots e base derivada.", no_args_is_help=True
)


@app.command()
def ingerir(
    destino: Annotated[Path, typer.Option(help="Pasta de saída.")] = Path("dados/snapshots/novo"),
    opcionais: Annotated[bool, typer.Option(help="Inclui as fontes opcionais.")] = False,
) -> None:
    """Baixa os arquivos do bucket do ONS e escreve manifesto.json e NOTAS.md."""
    m = ingestao.ingerir(destino, incluir_opcionais=opcionais, informar=typer.echo)
    typer.echo(f"{len(m.arquivos)} arquivos, {m.tamanho_total / 1e6:.1f} MB, em {destino}")


@app.command()
def comparar(anterior: Path, novo: Path) -> None:
    """Compara dois manifestos pelo sha256. Sai com 0 se iguais, 1 se diferentes."""
    d = manifesto.comparar(manifesto.carregar(anterior), manifesto.carregar(novo))
    for rotulo, chaves in (("novo", d.novos), ("removido", d.removidos), ("alterado", d.alterados)):
        for chave in chaves:
            typer.echo(f"{rotulo}: {chave}")
    if d.iguais:
        typer.echo("iguais")
        return
    raise typer.Exit(code=1)


@app.command()
def baixar(
    tag: Annotated[
        str, typer.Option(help="Tag da release (snapshot/AAAA-MM-DD) ou latest.")
    ] = "latest",
    destino: Annotated[Path, typer.Option(help="Pasta dos snapshots.")] = Path("dados/snapshots"),
    repo: Annotated[str | None, typer.Option(help="dono/repo. Padrão: SNAPSHOT_REPO.")] = None,
) -> None:
    """Baixa um snapshot publicado como release e confere os hashes."""
    if not token_do_github():
        typer.echo(
            "sem GITHUB_TOKEN: só funciona se o repositório for público, e o do ARCO não é. "
            "Ponha a chave no `.env` da raiz — com o gh instalado, "
            "`printf '\\nGITHUB_TOKEN=%s\\n' \"$(gh auth token)\" >> .env`.",
            err=True,
        )
    pasta = releases.baixar_release(tag=tag, destino=destino, repo=repo, informar=typer.echo)
    typer.echo(f"snapshot pronto em {pasta}")


def _extrator() -> _preparar.Extrator:
    """Liga `ia` ao preparo, importado só aqui: `dados` roda sem `ia` instalado."""
    from arco_dados.texto import EquipamentoCitado, chave_subestacao
    from arco_ia.extrair import extrair as ler_com_modelo

    def extrator(texto: str) -> list[EquipamentoCitado]:
        lido = ler_com_modelo(texto)
        return [
            EquipamentoCitado(
                tensao_kv=e.tensao_kv,
                de=chave_subestacao(e.de),
                para=chave_subestacao(e.para),
                ordem_circuito=e.ordem_circuito,
                codigo_circuito=e.codigo_circuito,
                papel=e.papel,
                de_exibicao=e.de,
                para_exibicao=e.para,
            )
            for e in lido.equipamentos
        ]

    return extrator


@app.command()
def preparar(
    snapshot: Annotated[Path, typer.Option(help="Pasta do snapshot.")],
    com_modelo: Annotated[
        bool,
        typer.Option(
            "--com-modelo",
            help="Manda ao modelo os textos que a regra não leu. Exige GEMINI_API_KEY.",
        ),
    ] = False,
) -> None:
    """Snapshot → artefatos derivados em arquivo. Feature 02, mais o resíduo da 08.

    Sem `--com-modelo` o preparo roda inteiro por regra, offline e sem chave. Com a opção, os
    textos que a regra não lê vão ao modelo, e a proposta dele passa pela mesma conferência
    contra o cadastro: é ela que autoriza o vínculo, não quem leu o texto.
    """
    resumo = _preparar.preparar(snapshot, extrator=_extrator() if com_modelo else None)
    typer.echo(
        f"{resumo.restricoes} restrições"
        + (
            f" (de {resumo.textos} textos: o ONS escreveu o mesmo gargalo de mais de um jeito)"
            if resumo.textos > resumo.restricoes
            else ""
        )
        + f", {resumo.intervalos} meias horas, "
        f"{resumo.propostas} propostas de vínculo "
        f"({resumo.casadas} com candidato, {resumo.sem_casamento} sem). "
        "Só a casada entra sozinha; o resto espera alguém resolver."
    )
    if resumo.fora_do_escopo:
        motivos = ", ".join(f"{n} {motivo}" for motivo, n in sorted(resumo.fora_do_escopo.items()))
        typer.echo(f"Fora do escopo, não ingeridos: {motivos}.")
    # O indeterminado é o único jeito de descobrir linha de verdade que a regra não reconhece.
    # Por isso ele é impresso, e não só contado: ninguém vai abrir tabela para procurar.
    if resumo.indeterminados:
        typer.secho(
            f"ATENÇÃO: {len(resumo.indeterminados)} texto(s) que o classificador de escopo não "
            "soube ler. Ficaram de fora. Se algum for linha de transmissão, a regra em "
            "`escopo()` precisa crescer:",
            fg=typer.colors.YELLOW,
        )
        for texto in resumo.indeterminados:
            typer.echo(f"  - {texto}")
