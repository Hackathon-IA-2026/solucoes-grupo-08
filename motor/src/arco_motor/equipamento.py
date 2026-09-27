"""Modalidade equipamento: efeito da adição de circuito sobre a série de corte.

Regra (premissa `sensibilidade_equipamento`, não verificada): em cada meia hora o ganho de
limite captura potência até `ganho_limite_mw x sensibilidade x disponibilidade`, limitado
pelo que foi cortado. A conversão entre capacidade e corte evitado é premissa visível e
editável; enquanto não validada, o resultado é estimativa contrafactual, com aviso.

Correção de minutos (premissa `correcao_minutos`, ligada por padrão): a energia da meia hora
é a média dos 30 minutos, mas o corte pode ter durado menos. Quando `minutos_cnf` está
preenchido, a potência que a alavanca enfrenta é o pico daqueles minutos, não a média, e o
que ela captura vale só durante eles. A correção mexe na potência capturada, **nunca** na
energia cortada da meia hora, que é a apuração oficial do ONS.
"""

from __future__ import annotations

from arco_motor.premissas import Premissas
from arco_motor.tipos import PASSO_HORAS, ConfigEquipamento, Intervalo, SerieRestricao

MINUTOS_NO_PASSO = 60.0 * PASSO_HORAS


def fator_pico(intervalo: Intervalo, corrigir: bool) -> float:
    """Quantas vezes o pico supera a média da meia hora. 1,0 quando não há correção.

    Vazio, zero ou 30 minutos significam sem correção: `minutos_cnf` ausente é dado que não
    veio, e não afirmação de que o corte durou a meia hora inteira.
    """
    minutos = intervalo.minutos_cnf
    if not corrigir or minutos is None or minutos <= 0 or minutos >= MINUTOS_NO_PASSO:
        return 1.0
    return MINUTOS_NO_PASSO / minutos


def aplicar(
    serie: SerieRestricao, config: ConfigEquipamento, premissas: Premissas
) -> tuple[list[float], list[float]]:
    """Devolve (evitado_mw, residual_mw), em MW médios da meia hora, alinhados à série."""
    sensibilidade = float(premissas.valor("sensibilidade_equipamento"))
    corrigir = bool(premissas.valor("correcao_minutos"))
    capturavel_mw = config.ganho_limite_mw * sensibilidade * config.disponibilidade

    evitado_mw: list[float] = []
    residual_mw: list[float] = []
    for intervalo in serie.intervalos:
        fator = fator_pico(intervalo, corrigir)
        pico_mw = intervalo.corte_mw * fator
        # O que a alavanca captura no pico, trazido de volta para a média da meia hora.
        evitado = min(pico_mw, capturavel_mw) / fator
        evitado = min(evitado, intervalo.corte_mw)
        evitado_mw.append(evitado)
        residual_mw.append(intervalo.corte_mw - evitado)
    return evitado_mw, residual_mw
