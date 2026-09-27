"""Agrupamento de intervalos de corte em ocorrências.

Uma ocorrência é um episódio de corte: intervalos com corte, seguidos no tempo. Serve para
**auditoria** — abrir um episódio e conferir o que aconteceu naquela noite —, e o invariante
avisa que a contagem não é número de vitrine, porque é sensível a artefato de apuração: uma meia
hora titulada por outra razão parte em duas uma noite que fisicamente foi uma.

**A série é esparsa** (ver `SerieRestricao`): o ONS só registra a meia hora em que houve corte.
Por isso o que separa duas ocorrências é a distância entre os **carimbos de tempo**, nunca a
adjacência na lista. Agrupar por vizinhança de linha juntaria o corte de segunda com o de sexta
num episódio só.
"""

from __future__ import annotations

from datetime import timedelta

from arco_motor.premissas import Premissas
from arco_motor.tipos import PASSO_HORAS, Intervalo, Ocorrencia, SerieRestricao

PREMISSA_TOLERANCIA = "regra_ocorrencia_intervalos_tolerados"


def agrupar(serie: SerieRestricao, premissas: Premissas) -> list[Ocorrencia]:
    """Ocorrências da série, em ordem cronológica.

    Dois intervalos com corte pertencem à mesma ocorrência quando a distância entre os carimbos
    é de até `tolerados + 1` meias horas. Com a premissa em 0, que é o padrão do invariante,
    exige-se folga zero: exatamente 30 minutos entre um e o seguinte.

    Intervalo sem corte não entra em ocorrência nenhuma, e **com a tolerância em zero**, que é o
    padrão, separa as duas ao redor. Com tolerância acima de zero ele pode ficar dentro do
    episódio, como qualquer outra folga tolerada. Não é hipótese: o ONS registra meia hora com
    corte zero, 303 delas na eólica do snapshot de 2026-09-21. Esparsa não quer dizer que toda
    linha tenha corte.
    """
    tolerados = int(premissas.valor(PREMISSA_TOLERANCIA))
    if tolerados < 0:
        raise ValueError(f"{PREMISSA_TOLERANCIA} não pode ser negativa: {tolerados}")
    folga_maxima_horas = (tolerados + 1) * PASSO_HORAS

    ocorrencias: list[Ocorrencia] = []
    atual: list[Intervalo] = []
    for intervalo in serie.intervalos:
        if intervalo.corte_mw <= 0:
            continue
        if atual:
            distancia_horas = (intervalo.instante - atual[-1].instante).total_seconds() / 3600.0
            if distancia_horas > folga_maxima_horas:
                ocorrencias.append(_fechar(atual))
                atual = []
        atual.append(intervalo)
    if atual:
        ocorrencias.append(_fechar(atual))
    return ocorrencias


def _fechar(intervalos: list[Intervalo]) -> Ocorrencia:
    """O fim é o fecho da última meia hora, não o carimbo dela: uma ocorrência de um intervalo
    dura meia hora, e não zero."""
    return Ocorrencia(
        inicio=intervalos[0].instante,
        fim=intervalos[-1].instante + timedelta(hours=PASSO_HORAS),
        intervalos=len(intervalos),
        energia_mwh=sum(intervalo.corte_mwh for intervalo in intervalos),
        corte_medio_maximo_mw=max(intervalo.corte_mw for intervalo in intervalos),
    )
