import { LoaderCircle } from 'lucide-react'
import { useParams } from 'react-router'
import { useReports } from '@/features/saved-simulations/api/report'
import { useGenerateReport } from '@/features/saved-simulations/api/use-generate-report'
import { ReportsList } from '@/features/saved-simulations/components/report/reports-list'
import { useSimulationCrumb } from '@/features/saved-simulations/api/simulation-crumb'
import { Breadcrumbs } from '@/components/layout/breadcrumbs'

/** Os relatórios da simulação: lista, gera um novo e abre exatamente o escolhido. */
export default function SimulationReports() {
  const { simulacaoId } = useParams()
  const simulationId = Number(simulacaoId)
  const reports = useReports({ simulationId })
  const { generate, generating, error } = useGenerateReport(simulationId, reports)
  const simulationCrumb = useSimulationCrumb(simulationId)

  return (
    <div className="sim-page">
      <main className="mx-auto flex max-w-screen-2xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
        <Breadcrumbs
          items={[
            { label: 'Simulações', to: '/simulacoes' },
            simulationCrumb,
            { label: 'Relatórios' },
          ]}
        />

        <section className="flex flex-col gap-4 border-b border-(--sim-border) pb-7 sm:flex-row sm:items-end sm:justify-between">
          <h1 className="sim-display text-2xl font-semibold text-(--sim-brand-ink) sm:text-3xl">
            Relatórios
          </h1>
          <button
            type="button"
            onClick={generate}
            disabled={generating}
            className="sim-btn-primary gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {generating && (
              <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />
            )}
            {generating ? 'Gerando relatório…' : 'Gerar relatório'}
          </button>
        </section>

        {error && (
          <div
            role="alert"
            className="flex flex-col gap-3 rounded-lg border border-(--sim-alert) bg-(--sim-alert-soft) px-4 py-3 text-xs leading-5 text-(--sim-muted-foreground) sm:flex-row sm:items-center"
          >
            <span>Erro ao gerar relatório: {error.message}</span>
            <button type="button" className="sim-btn-secondary" onClick={generate}>
              Tentar novamente
            </button>
          </div>
        )}

        <ReportsList simulationId={simulationId} reports={reports} />
      </main>
    </div>
  )
}
