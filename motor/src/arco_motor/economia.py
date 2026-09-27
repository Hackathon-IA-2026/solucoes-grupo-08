"""Conta econômica: fluxo de caixa anual, VPL, TIR, payback e custo por MWh.

Regras:
- beneficio_bruto(t) = energia recuperada no ano x preço da energia;
- fluxo_liquido(t) = beneficio_bruto(t) + receitas_adicionais(t) - opex(t) - reposicoes(t);
- CAPEX no ano zero; valor residual somado no último ano do horizonte;
- VPL com a taxa informada; TIR quando existe; payback simples e descontado, interpolados
  dentro do ano em que o acumulado cruza zero;
- período diferente de 12 meses anualizado conforme a premissa `anualizacao`, hoje dormente
  porque o período está travado em 12 meses completos.

O preço é um valor fixo em reais por MWh, não série temporal: o CMO saiu da ingestão em
2026-09-17 e sobrou como fonte do valor de partida.

A métrica não tem dono. A ferramenta não atribui a receita a nenhum agente, então isto é o
VPL **do investimento**, e não "do investidor" nem "socioeconômico".
"""

from __future__ import annotations

from arco_motor.premissas import Premissas
from arco_motor.tipos import ConfigFinanceira, FluxoAnual, ResultadoFinanceiro, ResultadoTecnico

MESES_NO_ANO = 12.0
_TIR_MIN = -0.9999
_TIR_MAX = 10.0
_TIR_PASSOS = 200


def vpl(fluxos_reais: list[float], taxa_aa: float) -> float:
    """VPL de fluxos anuais; o índice 0 é o ano zero (investimento), sem desconto."""
    return sum(fluxo / (1.0 + taxa_aa) ** ano for ano, fluxo in enumerate(fluxos_reais))


def tir(fluxos_reais: list[float]) -> float | None:
    """Taxa interna de retorno ao ano, ou None quando não existe no intervalo procurado.

    Bissecção entre -99,99% e 1.000% ao ano. Sem troca de sinal no fluxo não há raiz, e o
    motor devolve None em vez de um número inventado.
    """
    if not any(f > 0 for f in fluxos_reais) or not any(f < 0 for f in fluxos_reais):
        return None
    baixo, alto = _TIR_MIN, _TIR_MAX
    valor_baixo = vpl(fluxos_reais, baixo)
    if valor_baixo * vpl(fluxos_reais, alto) > 0:
        return None
    for _ in range(_TIR_PASSOS):
        meio = (baixo + alto) / 2.0
        valor_meio = vpl(fluxos_reais, meio)
        if valor_baixo * valor_meio <= 0:
            alto = meio
        else:
            baixo, valor_baixo = meio, valor_meio
    return (baixo + alto) / 2.0


def _cruzamento_de_zero(acumulados: list[float]) -> float | None:
    """Ano em que o acumulado passa de negativo para não negativo, interpolado no ano."""
    for ano, acumulado in enumerate(acumulados):
        if acumulado >= 0:
            if ano == 0:
                return 0.0
            anterior = acumulados[ano - 1]
            passo = acumulado - anterior
            if passo <= 0:
                return float(ano)
            return (ano - 1) + (-anterior / passo)
    return None


def calcular(
    tecnico: ResultadoTecnico,
    config: ConfigFinanceira,
    meses_no_periodo: float,
    premissas: Premissas,
) -> ResultadoFinanceiro:
    """Fluxo de caixa e indicadores, a partir da energia recuperada no período histórico."""
    if config.preco_energia_reais_mwh is not None:
        preco_reais_mwh = config.preco_energia_reais_mwh
    else:
        preco_reais_mwh = float(premissas.valor("preco_energia"))

    anualizar = premissas.valor("anualizacao") == "proporcional" and meses_no_periodo > 0
    fator_ano = MESES_NO_ANO / meses_no_periodo if anualizar else 1.0
    energia_ano_mwh = tecnico.energia_recuperada_mwh * fator_ano

    beneficio_bruto_ano = energia_ano_mwh * preco_reais_mwh
    opex_ano = config.opex_fixo_reais_ano + config.opex_variavel_reais_mwh * energia_ano_mwh
    reposicao_por_ano = {r.ano: r.valor_reais for r in config.reposicoes}

    fluxos: list[FluxoAnual] = []
    liquidos: list[float] = []
    acumulado = 0.0
    acumulado_descontado = 0.0

    for ano in range(config.horizonte_anos + 1):
        if ano == 0:
            bruto = receitas = opex = 0.0
            reposicao = config.capex_reais
            liquido = -config.capex_reais
        else:
            bruto = beneficio_bruto_ano
            receitas = config.receitas_adicionais_reais_ano
            opex = opex_ano
            reposicao = reposicao_por_ano.get(ano, 0.0)
            liquido = bruto + receitas - opex - reposicao
            if ano == config.horizonte_anos:
                liquido += config.valor_residual_reais

        descontado = liquido / (1.0 + config.taxa_desconto_aa) ** ano
        acumulado += liquido
        acumulado_descontado += descontado
        liquidos.append(liquido)
        fluxos.append(
            FluxoAnual(
                ano=ano,
                beneficio_bruto_reais=bruto,
                receitas_adicionais_reais=receitas,
                opex_reais=opex,
                reposicoes_reais=reposicao if ano > 0 else 0.0,
                fluxo_liquido_reais=liquido,
                fluxo_descontado_reais=descontado,
                acumulado_reais=acumulado,
                acumulado_descontado_reais=acumulado_descontado,
            )
        )

    energia_no_horizonte_mwh = energia_ano_mwh * config.horizonte_anos
    custos_totais = config.capex_reais + sum(f.opex_reais + f.reposicoes_reais for f in fluxos[1:])
    custo_por_mwh = (
        custos_totais / energia_no_horizonte_mwh if energia_no_horizonte_mwh > 0 else None
    )

    return ResultadoFinanceiro(
        vpl_reais=vpl(liquidos, config.taxa_desconto_aa),
        tir_aa=tir(liquidos),
        payback_simples_anos=_cruzamento_de_zero([f.acumulado_reais for f in fluxos]),
        payback_descontado_anos=_cruzamento_de_zero([f.acumulado_descontado_reais for f in fluxos]),
        custo_por_mwh_reais=custo_por_mwh,
        beneficio_bruto_reais=beneficio_bruto_ano * config.horizonte_anos,
        beneficio_liquido_reais=sum(liquidos),
        fluxos=fluxos,
    )
