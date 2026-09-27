"""Comandos da api: carga, semeadura, conferência e aprovação de vínculo.

`python -m arco_api.comandos <comando>`, ou pelos alvos do Makefile.

Desde a [ADR 0008] aprovar deixou de ser pré-requisito do produto: o casamento conferido contra
o cadastro entra sozinho, e o que chega aqui é o resíduo — o provável, o ambíguo e o que não
achou candidato. Rejeitar continua valendo como veto, e vale mais que a concordância do código.

A aprovação é comando de linha na v1, e não tela: tela de aprovação é feature 09. O que não é
opcional é a assinatura — aprovar exige o nome de quem aprovou, e, no caso ambíguo, qual dos
candidatos é o certo.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select

from arco_api.banco import sessao
from arco_api.carga import ResumoCarga, carregar, decidir, exportar, semear
from arco_api.modelos import PROPOSTO, REJEITADO, VALIDADO, Restricao, VinculoRestricaoEquipamento

SEMENTE = Path(__file__).resolve().parents[3] / "dados" / "vinculos" / "vinculos_validados.csv"


def _listar(apenas_pendentes: bool = True) -> int:
    with sessao() as s:
        consulta = select(VinculoRestricaoEquipamento).order_by(
            VinculoRestricaoEquipamento.restricao_id, VinculoRestricaoEquipamento.id
        )
        if apenas_pendentes:
            consulta = consulta.where(VinculoRestricaoEquipamento.status == PROPOSTO)
        vinculos = list(s.scalars(consulta))
        # A identidade guarda o primeiro texto visto, que é o que rotula a restrição aqui.
        textos = {r.id: r.texto for r in s.scalars(select(Restricao))}
        for v in vinculos:
            texto = textos.get(v.restricao_id, "")
            print(f"[{v.id:>4}] {v.situacao:<14} {v.papel:<15} {v.citacao}")
            print(f"       proposto: {v.cod_equipamento or '—'}")
            if v.candidatos:
                print(f"       candidatos: {v.candidatos.replace('|', '  ou  ')}")
            print(f"       texto: {texto[:110]}")
            print()
        print(f"{len(vinculos)} vínculo(s) {'pendente(s)' if apenas_pendentes else 'no total'}.")
        return len(vinculos)


def _relatar_mudanca(resumo: ResumoCarga) -> None:
    """O que entrou e o que saiu em relação ao snapshot anterior.

    Restrição que some não é erro — pode ter deixado de cortar, ou o ONS pode ter reescrito o
    texto e ela ter virado outra. O que não pode é sumir calada, levando junto vínculo assinado.
    """
    if resumo.restricoes_novas:
        print(f"\n{len(resumo.restricoes_novas)} restrição(ões) nova(s) neste snapshot.")
    if not resumo.restricoes_sumidas:
        return
    print(f"\n{len(resumo.restricoes_sumidas)} restrição(ões) que o snapshot anterior media:")
    for sumida in resumo.restricoes_sumidas:
        marca = "  ⚠ TINHA VÍNCULO" if sumida.tinha_vinculo else ""
        print(f"\n  [{sumida.restricao_id}]{marca}")
        print(f"       {sumida.texto[:110]}")
        for rid, texto, quanto in sumida.parecidas:
            print(f"       parecida {quanto:>4.0%}  [{rid}] {texto[:90]}")
        if not sumida.parecidas:
            print("       nenhuma restrição nova parecida")
    print("\nSemelhança é pista para quem confere, não religamento.")


def principal(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(prog="arco-api", description=__doc__)
    sub = analisador.add_subparsers(dest="comando", required=True)

    p_carregar = sub.add_parser("carregar", help="artefatos do preparo → banco, idempotente")
    p_carregar.add_argument("--artefatos", type=Path, required=True)
    p_carregar.add_argument("--nao-ativar", action="store_true")

    sub.add_parser("semear", help="aplica os vínculos validados do CSV versionado")
    sub.add_parser("exportar", help="grava os validados no CSV versionado, para entrar por PR")

    p_vinculos = sub.add_parser("vinculos", help="lista vínculos para conferência")
    p_vinculos.add_argument("--todos", action="store_true")

    p_decidir = sub.add_parser("aprovar", help="aprova ou rejeita um vínculo")
    p_decidir.add_argument("id", type=int)
    p_decidir.add_argument("--por", required=True, help="nome de quem está assinando")
    p_decidir.add_argument("--rejeitar", action="store_true")
    p_decidir.add_argument("--observacao")
    p_decidir.add_argument(
        "--escolher",
        metavar="COD",
        help="código do equipamento, para desempatar proposta ambígua",
    )

    args = analisador.parse_args(argumentos)

    if args.comando == "carregar":
        resumo = carregar(args.artefatos, ativar=not args.nao_ativar)
        print(
            f"snapshot {resumo.snapshot_id}: {resumo.restricoes} restrições, "
            f"{resumo.equipamentos} equipamentos, {resumo.intervalos} meias horas. "
            f"Vínculos: {resumo.vinculos_novos} novos, {resumo.vinculos_atualizados} "
            f"atualizados, {resumo.vinculos_preservados} preservados por já terem assinatura."
        )
        _relatar_mudanca(resumo)
    elif args.comando == "semear":
        if not SEMENTE.exists():
            print(f"Sem semente em {SEMENTE}: nenhum vínculo validado, e o ranking fica vazio.")
        print(f"{semear(SEMENTE)} vínculo(s) validado(s) aplicado(s) de {SEMENTE.name}")
    elif args.comando == "exportar":
        print(f"{exportar(SEMENTE)} vínculo(s) validado(s) gravado(s) em {SEMENTE}")
    elif args.comando == "vinculos":
        _listar(apenas_pendentes=not args.todos)
    elif args.comando == "aprovar":
        try:
            alvo = decidir(
                args.id,
                REJEITADO if args.rejeitar else VALIDADO,
                validado_por=args.por,
                observacao=args.observacao,
                cod_equipamento=args.escolher,
            )
        except (ValueError, LookupError) as erro:
            print(f"não aprovado: {erro}")
            return 1
        print(
            f"vínculo {alvo.id}: {alvo.status} em {alvo.cod_equipamento} "
            f"por {alvo.validado_por} em {alvo.validado_em}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
