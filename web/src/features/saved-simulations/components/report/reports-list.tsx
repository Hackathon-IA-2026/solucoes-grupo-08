import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import {
  getReportQueryOptions,
  type ReportListItem,
  type ReportOpenState,
  type useReports,
} from '../../api/report'
import { StateBadge } from './report-header'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime, formatInteger, formatRevisionRange } from '@/utils/format'

// O contrato não traz um campo "indisponível". `falhou` é o único estado em que a API diz que o
// relatório não chegou ao fim (`erro`) e não há conteúdo para ler: esse é listado, mas não abre.
// `barrado` tem a parte calculada e `gerando` abre no carregamento, então ambos podem ser vistos.
const isViewable = (report: ReportListItem) => report.estado !== 'falhou'

function ReportRow({ simulationId, report }: { simulationId: number; report: ReportListItem }) {
  const queryClient = useQueryClient()
  // Já na intenção de abrir, a leitura começa: ao chegar na tela, o relatório costuma estar pronto.
  const prefetch = () =>
    void queryClient.prefetchQuery(getReportQueryOptions(simulationId, report.id))
  const openState: ReportOpenState = { generated: report.estado !== 'gerando' }

  const newRevisions = report.revisoes_novas.length
  const viewable = isViewable(report)

  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 px-5 py-4">
      <div className="flex min-w-0 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="sim-display text-sm font-semibold text-(--sim-brand-ink)">
            Relatório {report.id}
          </span>
          <StateBadge state={report.estado} />
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-(--sim-muted-foreground)">
          <span>{report.gerado_em ? formatDateTime(report.gerado_em) : 'Em geração'}</span>
          <span aria-hidden="true">·</span>
          <span>{formatRevisionRange(report.revisoes_cobertas)}</span>
          {newRevisions > 0 && (
            <span className="sim-tag normal-case tabular-nums">
              {formatInteger(newRevisions)} {newRevisions === 1 ? 'Revisão nova' : 'Revisões novas'}
            </span>
          )}
        </div>
      </div>

      {viewable ? (
        <Link
          to={`/simulacoes/${simulationId}/relatorios/${report.id}`}
          state={openState}
          onMouseEnter={prefetch}
          onFocus={prefetch}
          aria-label={`Visualizar relatório ${report.id}`}
          className="sim-btn-secondary"
        >
          Visualizar
        </Link>
      ) : (
        <div className="flex flex-col items-end gap-1 text-xs text-(--sim-muted-foreground)">
          <button
            type="button"
            disabled
            className="sim-btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
          >
            Indisponível
          </button>
          <span>Não é possível visualizar</span>
        </div>
      )}
    </li>
  )
}

function ReportsSkeleton() {
  return (
    <ul className="divide-y divide-(--sim-border)" aria-label="Carregando relatórios">
      {[0, 1, 2].map((row) => (
        <li key={row} className="flex items-center justify-between gap-4 px-5 py-4">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <Skeleton className="h-3.5 w-48" />
          </div>
          <Skeleton className="h-9 w-24" />
        </li>
      ))}
    </ul>
  )
}

/** O miolo da lista de relatórios: contagem, carregamento, erro, vazio e as linhas. Serve à página e ao modal. */
export function ReportsList({
  simulationId,
  reports,
}: {
  simulationId: number
  reports: ReturnType<typeof useReports>
}) {
  const count = reports.data?.length
  return (
    <section aria-label="Lista de relatórios" className="sim-card">
      {count !== undefined && count > 0 && (
        <div className="sim-card-head flex items-center justify-between gap-3 border-b border-(--sim-border) px-5 py-3">
          <p className="text-xs font-semibold text-(--sim-brand-ink)">
            {count} {count === 1 ? 'relatório' : 'relatórios'}
          </p>
        </div>
      )}

      {reports.isPending ? (
        <ReportsSkeleton />
      ) : reports.isError ? (
        <div
          role="alert"
          className="flex flex-col gap-3 px-5 py-4 text-xs leading-5 text-(--sim-muted-foreground) sm:flex-row sm:items-center"
        >
          <span>Erro ao carregar relatórios: {reports.error.message}</span>
          <button type="button" className="sim-btn-secondary" onClick={() => reports.refetch()}>
            Tentar novamente
          </button>
        </div>
      ) : reports.data.length === 0 ? (
        <p className="px-5 py-12 text-center text-sm text-(--sim-muted-foreground)">
          Nenhum relatório encontrado
        </p>
      ) : (
        <ul className="divide-y divide-(--sim-border)">
          {reports.data.map((report) => (
            <ReportRow key={report.id} simulationId={simulationId} report={report} />
          ))}
        </ul>
      )}
    </section>
  )
}
