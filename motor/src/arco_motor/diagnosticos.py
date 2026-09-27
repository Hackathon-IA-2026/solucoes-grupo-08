"""Diagnósticos: o que o explorador lê para decidir a próxima variação. Feature 17, marco 1.

Só VPL e fração recuperada não dizem qual alavanca mexer
([regras do explorador](../../../docs/features/agentes/17-regras-do-explorador.md), seção 4).
Três leituras, todas contas sobre o que `simular` já produziu, sem premissa nova:

- **saturação da bateria**: em quantas meias horas com corte ela terminou cheia (falta
  capacidade) e quantos episódios de corte a pegaram ainda com carga do anterior (falta tempo
  para descarregar);
- **corte residual**: quanto corte sobrou, e em que hora do dia;
- **cruzamentos** entre revisões: onde o payback simples passa para dentro do horizonte e onde a
  TIR passa da taxa, com a revisão de cada lado — a regra das fronteiras do relatório, sem
  interpolar.

As duas primeiras são de uma revisão e saem com o resultado; a terceira é de um conjunto de
revisões e se calcula na leitura.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from arco_motor.bateria import teto_mwh
from arco_motor.relatorio import RevisaoCoberta, _menor_alavanca
from arco_motor.tipos import (
    PASSO_HORAS,
    Configuracao,
    CorteResidual,
    Diagnosticos,
    ResultadoTecnico,
    SaturacaoDaBateria,
    SerieRestricao,
)
from arco_motor.versao import METODO_VERSAO

MEIA_HORA = timedelta(hours=PASSO_HORAS)

TOLERANCIA_MWH = 1e-6
"""Folga de ponto flutuante para "cheia" e "vazia". Não é premissa: um milésimo de kWh."""


def diagnosticar(
    serie: SerieRestricao, config: Configuracao, tecnico: ResultadoTecnico
) -> Diagnosticos:
    """Os diagnósticos de uma revisão, a partir da série e do resultado técnico dela. Não lê
    premissa: tudo sai do que o cálculo já produziu e do tempo entre os carimbos."""
    residual_apos_equipamento = [
        cortado - evitado
        for cortado, evitado in zip(tecnico.cortado_mw, tecnico.evitado_equipamento_mw, strict=True)
    ]
    return Diagnosticos(
        metodo_versao=METODO_VERSAO,
        saturacao=_saturacao(serie, config, tecnico, residual_apos_equipamento)
        if config.bateria is not None
        else None,
        corte_residual=_corte_residual(serie, tecnico),
    )


def _saturacao(
    serie: SerieRestricao,
    config: Configuracao,
    tecnico: ResultadoTecnico,
    residual_apos_equipamento: list[float],
) -> SaturacaoDaBateria:
    """Cheia é o teto do despacho (`bateria.teto_mwh`), com a degradação acumulada até ali, e
    com corte sobrando na meia hora: a que fechou no teto sem perder nada não é falta de
    capacidade.

    Episódio é físico: meias horas com corte chegando à bateria, a 30 minutos uma da outra. Não
    usa a folga tolerada da premissa de ocorrência, que existe para artefato de apuração: a
    bateria descarrega em qualquer meia hora sem corte que chegue a ela. A carga com que o
    episódio começa é a do fim da primeira meia hora menos o que ela absorveu nela: o despacho
    desconta a folga antes de absorver, e numa meia hora com corte não há descarga.
    """
    bateria = config.bateria
    assert bateria is not None
    piso_mwh = bateria.soc_min * bateria.capacidade_mwh
    com_corte = cheia = episodios = vazia = 0
    absorvido_acumulado_mwh = 0.0
    anterior: datetime | None = None
    for intervalo, residual_eq, absorvido, soc, residual in zip(
        serie.intervalos,
        residual_apos_equipamento,
        tecnico.absorvido_bateria_mw,
        tecnico.soc_mwh,
        tecnico.residual_mw,
        strict=True,
    ):
        absorvido_mwh = absorvido * PASSO_HORAS
        if residual_eq > 0:
            com_corte += 1
            teto = teto_mwh(bateria, absorvido_acumulado_mwh)
            if soc >= teto - TOLERANCIA_MWH and residual * PASSO_HORAS > TOLERANCIA_MWH:
                cheia += 1
            if anterior is None or intervalo.instante - anterior != MEIA_HORA:
                episodios += 1
                if soc - absorvido_mwh <= piso_mwh + TOLERANCIA_MWH:
                    vazia += 1
            anterior = intervalo.instante
        else:
            anterior = None
        absorvido_acumulado_mwh += absorvido_mwh
    return SaturacaoDaBateria(
        meias_horas_com_corte=com_corte,
        meias_horas_cheia=cheia,
        fracao_cheia=cheia / com_corte if com_corte else None,
        episodios=episodios,
        episodios_comecaram_vazia=vazia,
        episodios_comecaram_com_carga=episodios - vazia,
    )


def _corte_residual(serie: SerieRestricao, tecnico: ResultadoTecnico) -> CorteResidual:
    por_hora = [0.0] * 24
    for intervalo, residual in zip(serie.intervalos, tecnico.residual_mw, strict=True):
        por_hora[intervalo.instante.hour] += residual * PASSO_HORAS
    return CorteResidual(
        energia_mwh=sum(tecnico.residual_mw) * PASSO_HORAS, por_hora_do_dia_mwh=por_hora
    )


class Cruzamento(BaseModel):
    """O par vizinho, na ordem da alavanca, em que a condição muda de lado."""

    antes_revisao_id: int = Field(
        description="A vizinha anterior da primeira que atinge, na ordem da alavanca. Se a "
        "condição não cresce com a alavanca, pode haver maior que também não atinge."
    )
    depois_revisao_id: int = Field(description="A primeira que atinge, na ordem da alavanca.")


class Cruzamentos(BaseModel):
    payback_no_horizonte: Cruzamento | None = Field(
        description="Onde o payback simples passa a caber no horizonte. `null` quando nenhuma "
        "revisão cruza: todas cabem, ou nenhuma cabe."
    )
    tir_acima_da_taxa: Cruzamento | None = Field(
        description="Onde a TIR passa da taxa de desconto. `null` quando nenhuma revisão cruza."
    )


def cruzamentos(revisoes: Sequence[RevisaoCoberta]) -> Cruzamentos:
    """Na ordem de "menor alavanca" do relatório (tamanho, depois investimento, depois
    posição), a primeira revisão que atinge e a vizinha anterior, que não atinge. A primeira
    que atinge é a mesma que a fronteira do relatório aponta; aqui ela vem com a do outro lado.

    Não interpola: a fronteira fica entre as duas revisões, em algum lugar que ninguém calculou.
    Se a menor alavanca já atinge, não há cruzamento observado.
    """
    if not revisoes:
        return Cruzamentos(payback_no_horizonte=None, tir_acima_da_taxa=None)
    ordem = sorted(revisoes, key=_menor_alavanca(list(revisoes)))

    def no_horizonte(r: RevisaoCoberta) -> bool:
        payback = r.resultado.financeiro.payback_simples_anos
        return payback is not None and payback <= r.configuracao.financeira.horizonte_anos

    def acima_da_taxa(r: RevisaoCoberta) -> bool:
        tir = r.resultado.financeiro.tir_aa
        return tir is not None and tir > r.configuracao.financeira.taxa_desconto_aa

    return Cruzamentos(
        payback_no_horizonte=_cruzamento(ordem, no_horizonte),
        tir_acima_da_taxa=_cruzamento(ordem, acima_da_taxa),
    )


def _cruzamento(
    ordem: list[RevisaoCoberta], atinge: Callable[[RevisaoCoberta], bool]
) -> Cruzamento | None:
    primeira = next((k for k, r in enumerate(ordem) if atinge(r)), None)
    if primeira is None or primeira == 0:
        return None
    return Cruzamento(
        antes_revisao_id=ordem[primeira - 1].revisao_id,
        depois_revisao_id=ordem[primeira].revisao_id,
    )
