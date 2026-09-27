"""Contas de leitura que as rotas de restrição devolvem prontas.

A interface não faz conta: energia por fonte, fatia do total e agregação da série saem daqui.
Tudo parte da série semi-horária, que é esparsa — só existe linha onde houve corte — e por isso
a janela vem do snapshot, nunca da contagem de linhas.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from arco_api.modelos import SerieRestricao

HORAS_POR_INTERVALO = 0.5


class Fonte(StrEnum):
    EOLICA = "eolica"
    SOLAR = "solar"
    AMBAS = "ambas"


class Agregacao(StrEnum):
    MEIA_HORA = "meia_hora"
    DIA = "dia"
    SEMANA = "semana"
    MES = "mes"


def energia_por_restricao(s: Session, snapshot_id: str, fonte: Fonte) -> dict[str, float]:
    """Energia cortada em MWh de cada restrição, na fonte pedida. `ambas` soma as duas."""
    consulta = (
        select(SerieRestricao.restricao_id, func.sum(SerieRestricao.corte_mw))
        .where(SerieRestricao.snapshot_id == snapshot_id)
        .group_by(SerieRestricao.restricao_id)
    )
    if fonte is not Fonte.AMBAS:
        consulta = consulta.where(SerieRestricao.fonte == fonte.value)
    return {
        restricao_id: float(soma_mw or 0.0) * HORAS_POR_INTERVALO
        for restricao_id, soma_mw in s.execute(consulta).all()
    }


def fontes_com_serie(s: Session, snapshot_id: str, restricao_id: str) -> list[str]:
    """Fontes de geração que têm ao menos uma meia hora de corte nesta restrição."""
    return sorted(
        s.scalars(
            select(SerieRestricao.fonte)
            .where(
                SerieRestricao.snapshot_id == snapshot_id,
                SerieRestricao.restricao_id == restricao_id,
            )
            .distinct()
        ).all()
    )


def meias_horas(inicio: datetime | None, fim: datetime | None) -> int | None:
    """Quantas meias horas a janela declarada tem. `None` quando o snapshot não declara janela."""
    if inicio is None or fim is None:
        return None
    return int((fim - inicio) / timedelta(minutes=30))


def inicio_do_balde(instante: datetime, agregacao: Agregacao) -> datetime:
    dia = instante.replace(hour=0, minute=0, second=0, microsecond=0)
    if agregacao is Agregacao.DIA:
        return dia
    if agregacao is Agregacao.SEMANA:
        return dia - timedelta(days=dia.weekday())
    return dia.replace(day=1)


def _proximo(balde: datetime, agregacao: Agregacao) -> datetime:
    if agregacao is Agregacao.DIA:
        return balde + timedelta(days=1)
    if agregacao is Agregacao.SEMANA:
        return balde + timedelta(days=7)
    return (balde + timedelta(days=32)).replace(day=1)


def agregar(
    pontos: Iterable[tuple[datetime, float]],
    agregacao: Agregacao,
    inicio: datetime | None,
    fim: datetime | None,
) -> list[tuple[datetime, float]]:
    """Soma a energia por balde. Balde sem corte dentro da janela volta com zero.

    `fim` é exclusivo. Sem janela declarada, vale o que a série cobre.
    """
    energia: dict[datetime, float] = {}
    for instante, corte_mw in pontos:
        balde = inicio_do_balde(instante, agregacao)
        energia[balde] = energia.get(balde, 0.0) + corte_mw * HORAS_POR_INTERVALO
    if inicio is not None and fim is not None:
        balde = inicio_do_balde(inicio, agregacao)
        while balde < fim:
            energia.setdefault(balde, 0.0)
            balde = _proximo(balde, agregacao)
    return sorted(energia.items())
