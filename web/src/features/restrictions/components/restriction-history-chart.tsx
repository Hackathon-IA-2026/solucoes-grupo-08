import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, LabelList, XAxis, YAxis } from 'recharts'
import { useRestrictionSeries } from '../api/get-restriction-series'
import type { Source } from '../api/get-restrictions'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/utils/cn'
import { formatGWh, formatMWhAsGWh } from '@/utils/format'

type RestrictionHistoryChartProps = {
  restrictionId: string
  source: Source
}

type Granularity = 'mes' | 'semana' | 'dia'

const MONTHS_PT = [
  'jan',
  'fev',
  'mar',
  'abr',
  'mai',
  'jun',
  'jul',
  'ago',
  'set',
  'out',
  'nov',
  'dez',
]

/** Rótulo do eixo: "set/25" no mês, "02/10" na semana e no dia. */
export function tickLabel(iso: string, aggregation: Granularity) {
  const date = new Date(iso)
  if (aggregation === 'mes')
    return `${MONTHS_PT[date.getMonth()]}/${String(date.getFullYear()).slice(2)}`
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

/**
 * Mostra o número em cima da barra: em toda barra quando `labelEveryBar`, senão só a primeira e
 * a última. Extraída à parte porque `recharts` não expõe o layout num ambiente de teste sem
 * DOM real, então é ela, não o SVG renderizado, que carrega a cobertura de teste desta regra.
 */
export function shouldShowBarLabel(index: number, total: number, labelEveryBar: boolean) {
  return labelEveryBar || index === 0 || index === total - 1
}

// Largura média de um algarismo em `tabular-nums` a 11px, medida no navegador, contra a
// contagem só dos algarismos do rótulo — a vírgula (e o ponto de milhar, em valores maiores)
// é bem mais estreita que um algarismo, e contá-la como um algarismo inteiro superestimava a
// largura a ponto de nem o rótulo mais curto caber. `LABEL_GAP_PX` cobre a pontuação e o
// espaço mínimo até o rótulo vizinho, os dois juntos. Number em cada barra só cabe sem colidir
// quando a largura estimada do maior rótulo (o de mais algarismos, "143,6" pesa mais que "0,6")
// cabe na fatia de cada barra — daí "responsivo": muda com a largura real do gráfico, não com a
// granularidade escolhida, e com o valor maior da série, não com a contagem de barras.
const DIGIT_WIDTH_PX = 6
const LABEL_GAP_PX = 6

/** Só os algarismos de um rótulo formatado ("143,6" → 4): é isso, não o texto inteiro, que pesa. */
export function digitsIn(label: string) {
  return label.replace(/\D/g, '').length
}

/** Cabe um número por barra sem um encostar no vizinho, dado o espaço real disponível. */
export function fitsLabelPerBar(containerWidth: number, barCount: number, maxLabelDigits: number) {
  if (barCount === 0 || containerWidth === 0) return false
  const pxPerBar = containerWidth / barCount
  const estimatedLabelWidth = maxLabelDigits * DIGIT_WIDTH_PX + LABEL_GAP_PX
  return pxPerBar >= estimatedLabelWidth
}

const chartConfig = {
  energia_mwh: { label: 'Energia cortada', color: 'var(--sim-brand)' },
} satisfies ChartConfig

export function RestrictionHistoryChart({ restrictionId, source }: RestrictionHistoryChartProps) {
  const [aggregation, setAggregation] = useState<Granularity>('mes')
  const seriesQuery = useRestrictionSeries({ restrictionId, source, aggregation })

  // Ref de função, não `useRef`: a div só existe depois que a série carrega (antes disso a
  // tela mostra o spinner), então um `useRef` + `useEffect([])` mediria o nó de antes de ele
  // existir e nunca mais rodaria. Como estado, o efeito abaixo roda de novo sempre que o nó
  // aparece de verdade.
  const [chartElement, setChartElement] = useState<HTMLDivElement | null>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  useEffect(() => {
    // Sem `ResizeObserver` (ambiente de teste, navegador muito antigo), `containerWidth` fica em
    // 0 e `fitsLabelPerBar` cai no fallback seguro: só a primeira e a última barra.
    if (!chartElement || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver((entries) => {
      setContainerWidth(entries[0]?.contentRect.width ?? 0)
    })
    observer.observe(chartElement)
    return () => observer.disconnect()
  }, [chartElement])

  const buckets = seriesQuery.data?.baldes ?? []
  const totalMWh = buckets.reduce((sum, bucket) => sum + bucket.energia_mwh, 0)
  // Número em cada barra só quando a mais larga da série couber sem encostar na vizinha, dada a
  // largura real do gráfico agora — "143,6" pesa mais que "0,6", e a mesma semana que cabe numa
  // tela larga aperta numa estreita. Sem isso, ou fica número em toda barra sempre (colide com
  // valor grande) ou só primeira/última sempre (sobra espaço à toa com valor pequeno).
  const maxLabelDigits = Math.max(
    0,
    ...buckets.map((bucket) => digitsIn(formatMWhAsGWh(bucket.energia_mwh))),
  )
  const labelEveryBar = fitsLabelPerBar(containerWidth, buckets.length, maxLabelDigits)

  const granularities: { value: Granularity; label: string }[] = [
    { value: 'mes', label: 'Mês' },
    { value: 'semana', label: 'Semana' },
    { value: 'dia', label: 'Dia' },
  ]

  return (
    <section className="sim-card mt-5" aria-labelledby="serie-historica">
      <div className="flex flex-col gap-3 border-b border-(--sim-border) px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2
            id="serie-historica"
            className="sim-display text-base font-semibold text-(--sim-brand-ink)"
          >
            Série histórica do corte
          </h2>
          {buckets.length > 0 && (
            <p className="mt-1 text-xs text-(--sim-muted-foreground)">
              GWh cortados por{' '}
              {aggregation === 'mes' ? 'mês' : aggregation === 'semana' ? 'semana' : 'dia'} · total{' '}
              {formatMWhAsGWh(totalMWh)} GWh
            </p>
          )}
        </div>

        <div
          role="group"
          aria-label="Granularidade da série histórica"
          className="inline-flex w-fit rounded-md bg-(--sim-muted) p-1"
        >
          {granularities.map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={aggregation === item.value}
              onClick={() => setAggregation(item.value)}
              className={cn(
                'sim-filter-option',
                aggregation === item.value && 'sim-filter-option-active',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto px-4 pb-5 pt-6 sm:px-6">
        {seriesQuery.isPending ? (
          <div className="flex h-40 items-center justify-center">
            <Spinner />
          </div>
        ) : seriesQuery.isError ? (
          <p className="py-8 text-center text-sm text-warning">
            Não foi possível carregar a série: {seriesQuery.error.message}
          </p>
        ) : buckets.length === 0 ? (
          <p className="py-8 text-center text-sm text-(--sim-muted-foreground)">
            Sem corte registrado nesta janela e fonte.
          </p>
        ) : (
          <>
            <div ref={setChartElement}>
              <ChartContainer
                config={chartConfig}
                className="aspect-auto h-64 w-full min-w-[520px]"
              >
                <BarChart data={buckets} margin={{ top: 20 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="inicio"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    minTickGap={24}
                    tickFormatter={(value: string) => tickLabel(value, aggregation)}
                  />
                  {!labelEveryBar && (
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      width={48}
                      tickFormatter={(value: number) => formatGWh(value / 1000, 0)}
                    />
                  )}
                  <ChartTooltip
                    cursor={{ className: 'fill-muted' }}
                    content={
                      <ChartTooltipContent
                        indicator="line"
                        labelFormatter={(_, payload) =>
                          payload[0]
                            ? tickLabel(String(payload[0].payload.inicio), aggregation)
                            : ''
                        }
                        formatter={(value) => [`${formatMWhAsGWh(Number(value))} GWh`, ' cortados']}
                      />
                    }
                  />
                  <Bar
                    dataKey="energia_mwh"
                    fill="var(--color-energia_mwh)"
                    radius={[4, 4, 0, 0]}
                    barSize={24}
                    isAnimationActive={false}
                  >
                    <LabelList
                      dataKey="energia_mwh"
                      position="top"
                      content={(props) => {
                        const { x, y, width, value, index } = props
                        const shown = shouldShowBarLabel(
                          Number(index),
                          buckets.length,
                          labelEveryBar,
                        )
                        if (!shown || value == null) return null

                        return (
                          <text
                            x={Number(x) + Number(width) / 2}
                            y={Number(y) - 4}
                            textAnchor="middle"
                            fontSize={11}
                            fontWeight={500}
                            className="fill-(--sim-brand-ink) tabular-nums"
                          >
                            {formatMWhAsGWh(Number(value))}
                          </text>
                        )
                      }}
                    />
                  </Bar>
                </BarChart>
              </ChartContainer>
            </div>
          </>
        )}
      </div>
    </section>
  )
}
