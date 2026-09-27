"""Modalidade bateria: despacho sobre o corte residual.

Regra gulosa (premissa `despacho_bateria = gulosa`, não verificada): percorre a série em
ordem; se há corte residual, carrega até `potencia_mw` e até o espaço restante na capacidade
útil; se não há corte, descarrega até `potencia_mw`. O estado de carga passa de um intervalo
para o seguinte. A eficiência de ida e volta é aplicada na devolução. A disponibilidade
reduz a potência efetiva.

Duas premissas visíveis, e não omissões: a bateria só absorve energia que seria cortada,
nunca compra da rede; e a devolução usa a mesma linha sem esbarrar no limite da restrição,
o que não entra na conta.

A correção de minutos vale aqui pelo mesmo motivo que vale na alavanca de equipamento: se o
corte durou dez minutos, a potência que a bateria enfrenta é o triplo da média, e ela só
absorve durante aqueles minutos.

**A série é esparsa**, e a folga entre dois cortes não aparece como linha: aparece como
diferença entre dois carimbos de tempo. Duas meias horas de corte num dia significam 23 horas
de descanso, e é nelas que a bateria devolve o que guardou. O laço abaixo desconta esse tempo
antes de processar cada linha nova. Numa série densa a folga é sempre zero e nada muda.

A carga que sobra quando o histórico acaba não é devolvida: não houve mais tempo observado.
"""

from __future__ import annotations

from arco_motor.equipamento import fator_pico
from arco_motor.premissas import Premissas
from arco_motor.tipos import PASSO_HORAS, ConfigBateria, Intervalo


def capacidade_util_mwh(config: ConfigBateria, ciclos_acumulados: float) -> float:
    """Capacidade depois da degradação por ciclo acumulada até aqui.

    A degradação por calendário não entra: o cálculo técnico refaz um ano de histórico, e o
    envelhecimento ao longo do horizonte aparece na conta econômica, não na réplica.
    """
    fator = 1.0 - config.degradacao_por_ciclo * ciclos_acumulados
    return config.capacidade_mwh * max(fator, 0.0)


def teto_mwh(config: ConfigBateria, absorvido_acumulado_mwh: float) -> float:
    """A carga máxima permitida com a degradação acumulada até aqui: `soc_max` da capacidade
    útil, nunca abaixo do piso. É o "cheia" do despacho e dos diagnósticos."""
    ciclos = absorvido_acumulado_mwh / config.capacidade_mwh if config.capacidade_mwh > 0 else 0.0
    piso_mwh = config.soc_min * config.capacidade_mwh
    return max(piso_mwh, config.soc_max * capacidade_util_mwh(config, ciclos))


def simular(
    residual_mw: list[float],
    config: ConfigBateria,
    premissas: Premissas,
    intervalos: list[Intervalo] | None = None,
) -> tuple[list[float], list[float], list[float]]:
    """Devolve (absorvido_mw, devolvido_mw, soc_mwh), alinhados aos intervalos.

    `absorvido_mw` e `devolvido_mw` são MW médios da meia hora. `soc_mwh` é o estado de carga
    ao fim de cada intervalo. `intervalos` só é usado para os minutos da correção.
    """
    corrigir = bool(premissas.valor("correcao_minutos"))
    potencia_efetiva_mw = config.potencia_mw * config.disponibilidade
    piso_mwh = config.soc_min * config.capacidade_mwh
    soc_mwh = config.carga_inicial * config.capacidade_mwh
    absorvido_acumulado_mwh = 0.0

    absorvido: list[float] = []
    devolvido: list[float] = []
    soc: list[float] = []

    for k, residual in enumerate(residual_mw):
        if intervalos is not None and k > 0:
            distancia_horas = (
                intervalos[k].instante - intervalos[k - 1].instante
            ).total_seconds() / 3600.0
            folga_horas = distancia_horas - PASSO_HORAS
            if folga_horas > 0:
                # Meias horas sem corte que a série não materializa. A bateria devolve nelas.
                disponivel_mwh = max(soc_mwh - piso_mwh, 0.0)
                retirado_mwh = min(potencia_efetiva_mw * folga_horas, disponivel_mwh)
                soc_mwh -= retirado_mwh
                devolvido_na_folga_mwh = retirado_mwh * config.eficiencia_ida_volta
            else:
                devolvido_na_folga_mwh = 0.0
        else:
            devolvido_na_folga_mwh = 0.0

        teto = teto_mwh(config, absorvido_acumulado_mwh)

        absorvido_mw = 0.0
        devolvido_mw = 0.0

        if residual > 0:
            intervalo = intervalos[k] if intervalos is not None else None
            fator = fator_pico(intervalo, corrigir) if intervalo is not None else 1.0
            pico_residual_mw = residual * fator
            # O que a bateria captura no pico, trazido de volta para a média da meia hora.
            capturado_mw = min(potencia_efetiva_mw, pico_residual_mw) / fator
            espaco_mwh = max(teto - soc_mwh, 0.0)
            absorvido_mwh = min(capturado_mw * PASSO_HORAS, espaco_mwh)
            absorvido_mw = absorvido_mwh / PASSO_HORAS
            soc_mwh += absorvido_mwh
            absorvido_acumulado_mwh += absorvido_mwh
        else:
            disponivel_mwh = max(soc_mwh - piso_mwh, 0.0)
            retirado_mwh = min(potencia_efetiva_mw * PASSO_HORAS, disponivel_mwh)
            soc_mwh -= retirado_mwh
            devolvido_mw = retirado_mwh * config.eficiencia_ida_volta / PASSO_HORAS

        # O que a folga devolveu entra no intervalo que a fecha, porque é onde ela termina.
        devolvido_mw += devolvido_na_folga_mwh / PASSO_HORAS

        absorvido.append(absorvido_mw)
        devolvido.append(devolvido_mw)
        soc.append(soc_mwh)

    return absorvido, devolvido, soc
