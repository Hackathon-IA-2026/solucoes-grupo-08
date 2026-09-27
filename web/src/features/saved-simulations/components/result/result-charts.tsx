import { useId } from 'react'
import type { Result } from '../../api/get-simulation'
import { formatNumber } from '@/utils/format'

const WIDTH = 1344
const LEFT = 56
const RIGHT = 1330
const MAX_POINTS = 480

/**
 * Para desenhar, uma série longa vira no máximo `MAX_POINTS` pontos, guardando o maior valor de
 * cada trecho para o pico não sumir. É só apresentação: os números da tela vêm da API.
 */
function forDrawing(series: number[]): number[] {
  if (series.length <= MAX_POINTS) return series
  const size = Math.ceil(series.length / MAX_POINTS)
  return Array.from({ length: Math.ceil(series.length / size) }, (_, index) =>
    Math.max(...series.slice(index * size, (index + 1) * size)),
  )
}

/** Um teto redondo para o eixo: 300, 500, 1.000... */
function axisCeiling(value: number): number {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  return Math.ceil(value / magnitude) * magnitude
}

type Layer = {
  series: number[]
  kind: 'area' | 'line'
  className: string
}

type SeriesChartProps = {
  layers: Layer[]
  height: number
  ariaLabel: string
  unit: string
  /** Teto do eixo, quando não é o maior valor da série (a capacidade da bateria, por exemplo). */
  ceiling?: number
  /** Quantos intervalos o eixo tem: 3 dão 0, 1/3, 2/3 e o teto. */
  intervals?: number
}

function SeriesChart({
  layers,
  height,
  ariaLabel,
  unit,
  ceiling,
  intervals = 3,
}: SeriesChartProps) {
  const drawn = layers.map((layer) => ({ ...layer, series: forDrawing(layer.series) }))
  const max = ceiling ?? axisCeiling(Math.max(0, ...drawn.flatMap((layer) => layer.series)))
  const top = 16
  const base = height - 50
  const y = (value: number) => base - (value / max) * (base - top)
  const ticks = Array.from({ length: intervals + 1 }, (_, step) => (max / intervals) * step)

  const path = (series: number[], closed: boolean) => {
    const step = series.length > 1 ? (RIGHT - LEFT) / (series.length - 1) : 0
    const points = series.map((value, index) => `${LEFT + index * step},${y(value)}`)
    return closed
      ? `M${LEFT},${base} L${points.join(' ')} L${RIGHT},${base} Z`
      : `M${points.join(' L')}`
  }

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${WIDTH} ${height}`}
      role="img"
      aria-label={ariaLabel}
      className="block"
    >
      {ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={LEFT}
            x2={RIGHT}
            y1={y(tick)}
            y2={y(tick)}
            className={tick === 0 ? 'stroke-text-muted' : 'stroke-border'}
          />
          <text
            x={LEFT - 8}
            y={y(tick) + 4}
            textAnchor="end"
            fontSize="11"
            className="fill-text-muted"
          >
            {formatNumber(tick)}
          </text>
        </g>
      ))}
      {drawn.map((layer, index) =>
        layer.kind === 'area' ? (
          <path key={index} d={path(layer.series, true)} className={layer.className} />
        ) : (
          <path
            key={index}
            d={path(layer.series, false)}
            fill="none"
            strokeWidth="2"
            className={layer.className}
          />
        ),
      )}
      <text x={LEFT} y={height - 8} fontSize="11" className="fill-text-muted">
        {unit}
      </text>
    </svg>
  )
}

type ResultChartsProps = {
  result: Result
  /** Capacidade da bateria, em MWh, que dá o teto do eixo do estado de carga. */
  batteryCapacityMwh: number | null
}

/**
 * As séries de `Resultado.tecnico`, uma posição por meia hora COM corte, em ordem cronológica. A
 * API não devolve o instante de cada posição, então não há como agregar por dia, semana ou mês:
 * isso depende de a rota trazer os carimbos de tempo.
 */
export function ResultCharts({ result, batteryCapacityMwh }: ResultChartsProps) {
  const { tecnico: technical } = result
  const titleId = useId()

  return (
    <section className="sim-panel lg:col-span-8" aria-labelledby={titleId}>
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <h2 id={titleId} className="sim-panel-title">
            Meia a meia hora
          </h2>
          <p className="sim-panel-subtitle">
            {formatNumber(technical.cortado_mw.length)} meias horas com corte, em ordem
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-xs font-medium text-(--sim-muted-foreground)">
          <span className="sim-legend">
            <i className="bg-(--sim-chart-history)" />
            Corte histórico
          </span>
          <span className="sim-legend">
            <i className="bg-(--sim-chart-residual)" />
            Corte residual
          </span>
          <span className="sim-legend">
            <i className="bg-(--sim-positive)" />
            Evitado
          </span>
        </div>
      </div>

      <div className="mt-2">
        <SeriesChart
          height={240}
          unit="MW por meia hora"
          ariaLabel="Corte, residual e evitado por meia hora"
          layers={[
            { series: technical.cortado_mw, kind: 'area', className: 'fill-(--sim-chart-history)' },
            {
              series: technical.residual_mw,
              kind: 'area',
              className: 'fill-(--sim-chart-residual)',
            },
            {
              series: technical.evitado_equipamento_mw,
              kind: 'line',
              className: 'stroke-(--sim-positive) [stroke-dasharray:6_5]',
            },
          ]}
        />
      </div>

      {batteryCapacityMwh !== null && (
        <>
          <div className="mt-3 flex items-center gap-3">
            <h3 className="text-sm font-semibold text-text-primary">Estado de carga da bateria</h3>
            <span className="text-sm text-text-muted">MWh</span>
          </div>
          <SeriesChart
            height={150}
            unit="MWh armazenados · eixo até a capacidade da bateria"
            ariaLabel="Estado de carga da bateria por meia hora"
            ceiling={batteryCapacityMwh}
            intervals={2}
            layers={[
              { series: technical.soc_mwh, kind: 'line', className: 'stroke-text-secondary' },
            ]}
          />
        </>
      )}
    </section>
  )
}
