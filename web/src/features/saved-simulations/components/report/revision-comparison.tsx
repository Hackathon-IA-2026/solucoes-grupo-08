import { LineChart } from 'lucide-react'
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Link } from 'react-router'
import type { Derived, RankingKey, Report, RevisionRow, Sensitivity } from '../../api/report'
import { modalityLabels, scenarioLabels } from '../../api/labels'
import {
  formatOptional,
  formatSigned,
  newestRow,
  newRevisionUrl,
  revisionLabel,
  rowsById,
} from './report-format'
import { SectionHeading, Unit } from './report-section'
import { cn } from '@/utils/cn'
import { formatFractionAsPercent, formatInteger, formatNumber } from '@/utils/format'

const rankings: Record<RankingKey, string> = {
  vpl: 'VPL',
  fracao_recuperada: 'Fração recuperada',
  payback_descontado: 'Payback descontado',
  custo_por_mwh: 'Custo por MWh',
}

const tabs = [
  { id: 'ranking', label: 'Ranking por métrica' },
  { id: 'diferencas', label: 'Diferenças vs base e anterior' },
  { id: 'sensibilidade', label: 'Sensibilidade observada' },
] as const
type TabId = (typeof tabs)[number]['id']

const NOT_REACHED = 'não atingida entre as revisões cobertas'

function Muted({ children = '—' }: { children?: ReactNode }) {
  return <span className="text-(--sim-muted-foreground)">{children}</span>
}

function Frame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-lg bg-(--sim-background) px-4 py-3">
      <span className="text-xs font-semibold text-(--sim-muted-foreground)">{title}</span>
      <span className="text-sm tabular-nums text-(--sim-brand-ink)">{children}</span>
    </div>
  )
}

function Frontiers({ derived, rows }: { derived: Derived; rows: Map<number, RevisionRow> }) {
  const {
    menor_alavanca_com_payback_no_horizonte: payback,
    maior_fracao_recuperada: fraction,
    tir_passa_taxa: irr,
  } = derived.fronteiras

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <Frame title="Menor alavanca com payback no horizonte">
        {payback ? (
          <>
            {revisionLabel(rows, payback.revisao_id)} · {payback.alavanca}
            <span className="block text-xs text-(--sim-muted-foreground)">
              payback simples {formatNumber(payback.payback_anos, 1)} anos, horizonte de{' '}
              {formatNumber(payback.horizonte_anos)} anos
            </span>
          </>
        ) : (
          <Muted>{NOT_REACHED}</Muted>
        )}
      </Frame>
      <Frame title="Maior fração recuperada, e a que custo">
        {fraction ? (
          <>
            {revisionLabel(rows, fraction.revisao_id)} · {formatFractionAsPercent(fraction.fracao)}{' '}
            <Unit>%</Unit>
            {fraction.custo_por_mwh_reais != null && (
              <span className="block text-xs text-(--sim-muted-foreground)">
                R$ {formatNumber(fraction.custo_por_mwh_reais)} por MWh recuperado
              </span>
            )}
          </>
        ) : (
          <Muted>{NOT_REACHED}</Muted>
        )}
      </Frame>
      <Frame title="Onde a TIR passa a taxa de desconto">
        {irr ? (
          <>
            a partir da {revisionLabel(rows, irr.revisao_id)}
            <span className="block text-xs text-(--sim-muted-foreground)">
              TIR {formatFractionAsPercent(irr.tir_aa)} % a.a. contra{' '}
              {formatFractionAsPercent(irr.taxa_desconto_aa)} % a.a.
            </span>
          </>
        ) : (
          <Muted>{NOT_REACHED}</Muted>
        )}
      </Frame>
    </div>
  )
}

function Ranking({ derived, rows }: { derived: Derived; rows: Map<number, RevisionRow> }) {
  const [key, setKey] = useState<RankingKey>('vpl')
  const ranking = derived.ordenacoes[key] ?? []

  return (
    <div className="flex flex-col gap-4">
      <Frontiers derived={derived} rows={rows} />
      <div className="flex flex-wrap items-center gap-2 text-xs text-(--sim-muted-foreground)">
        <span id="ordenar-por">Ordenar por</span>
        <div role="group" aria-labelledby="ordenar-por" className="flex flex-wrap gap-1.5">
          {(Object.keys(rankings) as RankingKey[]).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={key === option}
              onClick={() => setKey(option)}
              className={cn(
                'h-8 rounded-full border px-3 text-xs font-semibold transition-colors',
                key === option
                  ? 'border-(--sim-brand) bg-(--sim-sky-soft)/50 text-(--sim-brand-ink)'
                  : 'border-(--sim-border) bg-(--sim-surface) text-(--sim-foreground) hover:bg-(--sim-muted)',
              )}
            >
              {rankings[option]}
            </button>
          ))}
        </div>
      </div>
      <div className="relative overflow-x-auto">
        <table className="sim-list-table w-full min-w-230 text-xs tabular-nums">
          <thead>
            <tr>
              <th className="w-10">#</th>
              <th>Revisão</th>
              <th>Configuração</th>
              <th data-align="right">VPL (R$)</th>
              <th data-align="right">Fração recuperada</th>
              <th data-align="right">Payback simples</th>
              <th data-align="right">Custo por MWh recuperado</th>
              <th data-align="right">TIR</th>
              <th data-align="right">Avisos</th>
            </tr>
          </thead>
          <tbody>
            {ranking.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-6 text-center">
                  <Muted>Nenhuma revisão coberta tem esta métrica.</Muted>
                </td>
              </tr>
            ) : (
              ranking.map((item) => {
                const row = rows.get(item.revisao_id)
                return (
                  <tr key={item.revisao_id}>
                    <td>
                      <span className="sim-rank-number">{item.posicao}</span>
                      {item.empate_com.length > 0 && (
                        <span className="ml-1 text-(--sim-muted-foreground)">empate</span>
                      )}
                    </td>
                    <td className="whitespace-nowrap font-bold">
                      {row ? (
                        <Link to={row.url} className="text-(--sim-brand) hover:underline">
                          rev {item.posicao_da_revisao}
                        </Link>
                      ) : (
                        `rev ${item.posicao_da_revisao}`
                      )}
                    </td>
                    <td className="text-(--sim-foreground)">
                      {row
                        ? `${modalityLabels[row.modalidade]} · ${row.alavanca} · ${scenarioLabels[row.cenario]}`
                        : '—'}
                    </td>
                    <td data-align="right" className="font-semibold text-(--sim-brand-ink)">
                      {row ? formatNumber(row.vpl_reais, 2) : '—'}
                    </td>
                    <td data-align="right">
                      {row ? `${formatFractionAsPercent(row.fracao_recuperada)} %` : '—'}
                    </td>
                    <td data-align="right">
                      {row ? (
                        formatOptional(
                          row.payback_simples_anos,
                          (v) => `${formatNumber(v, 1)} anos`,
                        )
                      ) : (
                        <Muted />
                      )}
                    </td>
                    <td data-align="right">
                      {row ? (
                        formatOptional(row.custo_por_mwh_reais, (v) => `R$ ${formatNumber(v)}`)
                      ) : (
                        <Muted />
                      )}
                    </td>
                    <td data-align="right">
                      {row ? (
                        formatOptional(row.tir_aa, (v) => `${formatFractionAsPercent(v)} % a.a.`)
                      ) : (
                        <Muted />
                      )}
                    </td>
                    <td data-align="right">{row ? formatInteger(row.avisos) : '—'}</td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SignedCell({
  value,
  decimalPlaces = 0,
}: {
  value: number | null
  decimalPlaces?: number
}) {
  return (
    <td
      data-align="right"
      className={cn(
        'whitespace-nowrap',
        (value == null || value === 0) && 'text-(--sim-muted-foreground)',
      )}
    >
      {value == null ? '—' : formatSigned(value, decimalPlaces)}
    </td>
  )
}

function Differences({ derived, rows }: { derived: Derived; rows: Map<number, RevisionRow> }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="sim-list-table w-full min-w-250 text-xs tabular-nums">
        <thead>
          <tr>
            <th>Revisão</th>
            <th>O que mudou</th>
            <th data-align="right">ΔVPL vs base (R$)</th>
            <th data-align="right">ΔVPL vs anterior (R$)</th>
            <th data-align="right">Δenergia vs base (MWh)</th>
            <th data-align="right">Δenergia vs anterior (MWh)</th>
            <th data-align="right">Δfração vs base (p.p.)</th>
            <th data-align="right">Δpayback vs base (anos)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="whitespace-nowrap font-bold">rev {derived.base.posicao}</td>
            <td>
              <span className="sim-tag">Base</span>
            </td>
            {Array.from({ length: 6 }, (_, index) => (
              <td key={index} data-align="right">
                <Muted />
              </td>
            ))}
          </tr>
          {derived.diferencas.map((difference) => (
            <tr key={difference.revisao_id}>
              <td className="whitespace-nowrap font-bold">
                {revisionLabel(rows, difference.revisao_id)}
              </td>
              <td className="min-w-60 text-(--sim-foreground)">{difference.o_que_mudou}</td>
              <SignedCell value={difference.delta_vpl_vs_base_reais} />
              <SignedCell value={difference.delta_vpl_vs_anterior_reais} />
              <SignedCell value={difference.delta_energia_vs_base_mwh} />
              <SignedCell value={difference.delta_energia_vs_anterior_mwh} />
              <SignedCell value={difference.delta_fracao_vs_base * 100} decimalPlaces={1} />
              <SignedCell value={difference.delta_payback_simples_vs_base_anos} decimalPlaces={1} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SensitivityFrame({
  sensitivity,
  rows,
}: {
  sensitivity: Sensitivity
  rows: Map<number, RevisionRow>
}) {
  const pair = `${revisionLabel(rows, sensitivity.de_revisao_id)} → ${revisionLabel(rows, sensitivity.para_revisao_id)}`

  if (sensitivity.tipo === 'sem_par') {
    const changed = sensitivity.campos_que_mudaram
    return (
      <div className="flex flex-col gap-1 rounded-lg border border-dashed border-(--sim-border) px-4 py-3">
        <span className="text-xs font-semibold text-(--sim-muted-foreground)">{pair}</span>
        <span className="text-xs text-(--sim-muted-foreground)">
          {changed.length === 0
            ? 'Nada mudou entre as duas: recálculo da mesma configuração. Sem par de sensibilidade.'
            : changed.length === 1
              ? `1 campo mudou (${changed[0]}). Sem par de sensibilidade.`
              : `${changed.length} campos mudaram de uma vez (${changed.join(', ')}). Sem par de sensibilidade.`}
        </span>
      </div>
    )
  }

  // A unidade do campo vem no valor ("50 MW"): a razão é "por MW", "por MWh".
  const unit = sensitivity.para?.split(' ').slice(1).join(' ')

  return (
    <div className="flex flex-col gap-1 rounded-lg bg-(--sim-background) px-4 py-3">
      <span className="text-xs font-semibold text-(--sim-muted-foreground)">
        {pair} · {sensitivity.rotulo}
      </span>
      {sensitivity.tipo === 'numerica' ? (
        <>
          {sensitivity.delta_vpl_por_unidade_reais != null && (
            <span className="text-sm tabular-nums text-(--sim-brand-ink)">
              R$ {formatSigned(sensitivity.delta_vpl_por_unidade_reais)}{' '}
              <Unit>de VPL por {unit}</Unit>
            </span>
          )}
          {sensitivity.delta_energia_por_unidade_mwh != null && (
            <span className="text-sm tabular-nums text-(--sim-brand-ink)">
              {formatSigned(sensitivity.delta_energia_por_unidade_mwh)}{' '}
              <Unit>MWh recuperados por {unit}</Unit>
            </span>
          )}
          <span className="text-xs text-(--sim-muted-foreground)">
            {sensitivity.de} → {sensitivity.para}, {sensitivity.condicao}
          </span>
        </>
      ) : (
        <>
          {sensitivity.delta_vpl_reais != null && (
            <span className="text-sm tabular-nums text-(--sim-brand-ink)">
              R$ {formatSigned(sensitivity.delta_vpl_reais)} <Unit>de ΔVPL</Unit>
            </span>
          )}
          <span className="text-xs text-(--sim-muted-foreground)">
            {sensitivity.de} → {sensitivity.para}. Campo categórico: só a diferença, sem razão por
            unidade.
          </span>
        </>
      )}
    </div>
  )
}

function Sensitivities({ derived, rows }: { derived: Derived; rows: Map<number, RevisionRow> }) {
  if (derived.sensibilidades.length === 0) {
    return (
      <p className="text-sm text-(--sim-muted-foreground)">
        A sensibilidade compara pares de revisões que diferem num único parâmetro. Nenhum par
        coberto difere num só.
      </p>
    )
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {derived.sensibilidades.map((sensitivity) => (
        <SensitivityFrame
          key={`${sensitivity.de_revisao_id}-${sensitivity.para_revisao_id}`}
          sensitivity={sensitivity}
          rows={rows}
        />
      ))}
    </div>
  )
}

function EmptyComparison({ report }: { report: Report }) {
  const newest = newestRow(report)
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-dashed border-(--sim-border) p-5 sm:flex-row sm:items-center">
      <span
        className="grid size-10 shrink-0 place-items-center rounded-lg bg-(--sim-muted) text-(--sim-muted-foreground)"
        aria-hidden="true"
      >
        <LineChart className="size-5" />
      </span>
      <p className="grow text-sm leading-6 text-(--sim-foreground)">
        <strong className="text-(--sim-brand-ink)">
          Uma revisão só: não há diferenças nem sensibilidade para mostrar.
        </strong>{' '}
        Crie uma revisão mudando potência, capacidade ou ponto de conexão para ver o efeito de cada
        mudança.
      </p>
      {newest && (
        <Link
          to={newRevisionUrl(report.cabecalho?.restricao_id, newest.revisao_id)}
          className="sim-btn-secondary shrink-0"
        >
          Criar nova revisão
        </Link>
      )}
    </div>
  )
}

/** Ranking, diferenças e sensibilidade, tudo derivado por código, em abas de um cartão só. */
export function RevisionComparison({ report }: { report: Report }) {
  const [active, setActive] = useState<TabId>('ranking')
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const baseId = useId()
  const derived = report.derivados
  const rows = rowsById(report.por_revisao)
  const enough = report.por_revisao.length >= 2 && derived

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (step === 0) return
    event.preventDefault()
    const next = (index + step + tabs.length) % tabs.length
    setActive(tabs[next].id)
    buttons.current[next]?.focus()
  }

  return (
    <section aria-labelledby="comparacao" className="flex flex-col gap-3">
      <SectionHeading id="comparacao" title="Comparação entre revisões" />
      <div className="sim-card flex flex-col gap-4 p-4 sm:p-6">
        {!enough ? (
          <EmptyComparison report={report} />
        ) : (
          <>
            <div
              role="tablist"
              aria-label="Visões da comparação"
              className="flex w-fit max-w-full flex-wrap gap-1 rounded-md bg-(--sim-muted) p-1"
            >
              {tabs.map((tab, index) => (
                <button
                  key={tab.id}
                  ref={(element) => {
                    buttons.current[index] = element
                  }}
                  type="button"
                  role="tab"
                  id={`${baseId}-${tab.id}`}
                  aria-selected={active === tab.id}
                  aria-controls={`${baseId}-${tab.id}-panel`}
                  tabIndex={active === tab.id ? 0 : -1}
                  onClick={() => setActive(tab.id)}
                  onKeyDown={(event) => onKeyDown(event, index)}
                  className={cn(
                    'sim-filter-option h-9!',
                    active === tab.id && 'sim-filter-option-active',
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div
              role="tabpanel"
              id={`${baseId}-${active}-panel`}
              aria-labelledby={`${baseId}-${active}`}
            >
              {active === 'ranking' ? (
                <Ranking derived={derived} rows={rows} />
              ) : active === 'diferencas' ? (
                <Differences derived={derived} rows={rows} />
              ) : (
                <Sensitivities derived={derived} rows={rows} />
              )}
            </div>
          </>
        )}
      </div>
    </section>
  )
}
