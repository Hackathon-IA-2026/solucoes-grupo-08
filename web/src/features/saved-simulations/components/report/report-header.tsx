import { Check, CircleAlert, Clock, LoaderCircle, Zap } from 'lucide-react'
import { Link } from 'react-router'
import type { Report, ReportState } from '../../api/report'
import { Breadcrumbs } from '@/components/layout/breadcrumbs'
import { Badge } from '@/components/ui/badge'
import {
  formatDateTime,
  formatInteger,
  formatRevisionRange,
  formatSnapshotId,
} from '@/utils/format'

const stateBadges: Record<
  ReportState,
  { label: string; variant: 'success' | 'default' | 'danger' }
> = {
  pronto: { label: 'Pronto', variant: 'success' },
  gerando: { label: 'Gerando', variant: 'default' },
  barrado: { label: 'Barrado', variant: 'danger' },
  falhou: { label: 'Falhou', variant: 'danger' },
}

export function StateBadge({ state }: { state: ReportState }) {
  const { label, variant } = stateBadges[state]
  const Icon = state === 'pronto' ? Check : state === 'gerando' ? Clock : CircleAlert

  return (
    <Badge variant={variant} className="gap-1.5">
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </Badge>
  )
}

type ReportHeadingProps = {
  report: Report
  /** Onde "Abrir a simulação" leva: a revisão mais nova coberta. */
  simulationUrl: string
  onRequestNewReport: () => void
  requestingNewReport: boolean
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 px-4 py-3 first:pl-0 sm:py-0">
      <dt className="sim-eyebrow text-(--sim-muted-foreground)">{label}</dt>
      <dd className="truncate text-sm font-semibold tabular-nums text-(--sim-brand-ink)">
        {children}
      </dd>
    </div>
  )
}

/**
 * O relatório é da simulação: o nome dela é o título, e "Relatório" é o tipo do documento,
 * acima. Os metadados ficam numa faixa de pares rótulo/valor, que se lê de relance.
 */
export function ReportHeading({
  report,
  simulationUrl,
  onRequestNewReport,
  requestingNewReport,
}: ReportHeadingProps) {
  const covered = report.revisoes_cobertas.length
  const header = report.cabecalho
  const restrictionName = header ? (header.nome_curto ?? header.texto) : null

  return (
    <section className="flex flex-col gap-6 border-b border-(--sim-border) pb-7">
      <Breadcrumbs
        items={[
          { label: 'Simulações', to: '/simulacoes' },
          { label: report.nome, to: simulationUrl },
          { label: 'Relatórios', to: `/simulacoes/${report.simulacao_id}/relatorios` },
          { label: `Relatório ${report.id}` },
        ]}
      />

      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="sim-eyebrow text-(--sim-brand)">Relatório da simulação</span>
            <StateBadge state={report.estado} />
          </div>
          <h1 className="sim-display text-2xl font-semibold text-(--sim-brand-ink) sm:text-3xl">
            {report.nome}
          </h1>
          {header && restrictionName && (
            <Link
              to={`/restricoes/${header.restricao_id}`}
              title={header.texto}
              className="inline-flex w-fit items-center gap-1.5 text-sm text-(--sim-muted-foreground) hover:text-(--sim-brand)"
            >
              <Zap className="size-3.5 text-(--sim-brand)" aria-hidden="true" />
              {restrictionName}
              {header.instrucao_operacao && (
                <span className="sim-tag">{header.instrucao_operacao}</span>
              )}
            </Link>
          )}
          {report.pergunta && (
            <p className="mt-1 max-w-3xl border-l-2 border-(--sim-sky-soft) pl-3 text-sm italic leading-6 text-(--sim-foreground)">
              {report.pergunta}
            </p>
          )}
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <Link to={simulationUrl} className="sim-btn-secondary">
            Abrir a simulação
          </Link>
          <button
            type="button"
            onClick={onRequestNewReport}
            disabled={requestingNewReport}
            className="sim-btn-primary gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {requestingNewReport && (
              <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />
            )}
            Gerar relatório novo
          </button>
        </div>
      </div>

      <dl className="grid grid-cols-2 divide-(--sim-border) rounded-lg border border-(--sim-border) bg-(--sim-surface) px-4 py-3 sm:flex sm:divide-x sm:py-3.5">
        <Meta label="Gerado em">
          {report.gerado_em ? formatDateTime(report.gerado_em) : 'em geração'}
        </Meta>
        <Meta label="Dado do ONS">{formatSnapshotId(report.snapshot_id)}</Meta>
        <Meta label="Método">v{report.metodo_versao}</Meta>
        {report.modelo && (
          <Meta label="Modelo">
            <span className="font-mono text-[0.8125rem] font-medium">{report.modelo}</span>
          </Meta>
        )}
        <Meta label="Revisões">
          {formatInteger(covered)}{' '}
          <span className="font-normal text-(--sim-muted-foreground)">
            ({formatRevisionRange(report.revisoes_cobertas)})
          </span>
        </Meta>
      </dl>
    </section>
  )
}

/** Revisões criadas depois do relatório: ficam fora de todas as seções abaixo. */
export function NewRevisionsNotice({ report }: { report: Report }) {
  const newRevisions = report.revisoes_novas
  if (newRevisions.length === 0) return null

  return (
    <div
      role="note"
      className="flex flex-col gap-2 rounded-lg border border-(--sim-alert) bg-(--sim-alert-soft) px-4 py-3 sm:flex-row sm:items-start sm:gap-3"
    >
      <Badge variant="warning" className="w-fit shrink-0 gap-1.5">
        <CircleAlert className="h-3 w-3" aria-hidden="true" />
        {formatInteger(newRevisions.length)}{' '}
        {newRevisions.length === 1 ? 'revisão nova' : 'revisões novas'}
      </Badge>
      <p className="text-xs leading-5 text-(--sim-foreground)">
        Este relatório cobre {formatRevisionRange(report.revisoes_cobertas)}. Depois dele{' '}
        {newRevisions.length === 1 ? 'entrou a' : 'entraram'}{' '}
        {newRevisions.map((revision) => `rev ${revision.posicao}`).join(' e ')}, que não{' '}
        {newRevisions.length === 1 ? 'está' : 'estão'} em nenhuma seção abaixo. Um relatório novo{' '}
        {newRevisions.length === 1 ? 'a inclui' : 'as inclui'}.
      </p>
    </div>
  )
}
