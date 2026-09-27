import { useCallback, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import {
  useCreateReport,
  useReport,
  type ReportOpenState,
} from '@/features/saved-simulations/api/report'
import { ConfigMatrix } from '@/features/saved-simulations/components/report/config-matrix'
import { ConstraintDetails } from '@/features/saved-simulations/components/report/constraint-details'
import { CurtailmentContext } from '@/features/saved-simulations/components/report/curtailment-context'
import { ExplorationTrail } from '@/features/saved-simulations/components/report/exploration-trail'
import { ModelReading } from '@/features/saved-simulations/components/report/model-reading'
import {
  NewRevisionsNotice,
  ReportHeading,
} from '@/features/saved-simulations/components/report/report-header'
import {
  newestRow,
  newRevisionUrl,
  rowsById,
} from '@/features/saved-simulations/components/report/report-format'
import { ReportLoading } from '@/features/saved-simulations/components/report/report-loading'
import { ResultHero } from '@/features/saved-simulations/components/report/result-hero'
import { RevisionComparison } from '@/features/saved-simulations/components/report/revision-comparison'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

/**
 * Relatório da simulação (feature 17, task 17.6): compilado por código e pela `ia`, nunca calculado
 * no cliente. Uma instância por relatório (`key`), para o estado de "estava no cache?" não
 * atravessar de um relatório para outro. O relatório vem sempre do id na rota: escolher qual
 * abrir é da lista em `/simulacoes/:simulacaoId/relatorios`.
 */
export default function SimulationReport() {
  const { relatorioId } = useParams()
  return <ReportPage key={relatorioId} />
}

function ReportPage() {
  const { simulacaoId, relatorioId } = useParams()
  const simulationId = Number(simulacaoId)
  const navigate = useNavigate()

  const query = useReport({ simulationId, reportId: Number(relatorioId) })
  // Aberto pela lista ("Visualizar") com o relatório já gerado: nada a acompanhar, então sem as
  // etapas do carregamento. Só um indicador enquanto a leitura não chega.
  const openedGenerated = (useLocation().state as ReportOpenState | null)?.generated === true
  const createReport = useCreateReport({ simulationId })

  // As etapas só seguram a tela quando há geração a acompanhar: se o relatório esteve `gerando`
  // aqui, ele só aparece depois da última etapa, mesmo que fique pronto antes. Já pronto ao chegar
  // (aberto pela URL, pelo link do chat ou do cache), aparece assim que a API responde.
  const [sawGenerating, setSawGenerating] = useState(false)
  if (query.data?.estado === 'gerando' && !sawGenerating) setSawGenerating(true)
  const [lastStepReached, setLastStepReached] = useState(false)
  const markLastStep = useCallback(() => setLastStepReached(true), [])

  function requestNewReport() {
    createReport.mutate(undefined, {
      onSuccess: (created) => {
        navigate(`/simulacoes/${simulationId}/relatorios/${created.id}`)
      },
    })
  }

  if (query.isError) {
    return (
      <div className="mx-auto max-w-360 px-6 py-8">
        <p className="text-sm text-warning">
          Não foi possível carregar o relatório: {query.error.message}
        </p>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/simulacoes">Voltar para Simulações</Link>
        </Button>
      </div>
    )
  }

  // Enquanto o loader está na tela ele é a única coisa da página: nem cabeçalho, nem botões. Vale
  // para abrir o relatório, para o relatório que ainda está `gerando` e para o pedido de um novo
  // (do clique até a navegação para ele). Todos usam o mesmo elemento, então a sequência de
  // etapas não reinicia quando um cede a vez ao outro.
  const generating = query.data?.estado === 'gerando'
  const requestingNew = createReport.isPending || createReport.isSuccess
  if (openedGenerated && query.isPending && !requestingNew) {
    return (
      <div className="sim-page flex items-center justify-center px-4 py-16">
        <Spinner />
      </div>
    )
  }
  const waitLastStep = sawGenerating && !lastStepReached
  if (query.isPending || requestingNew || generating || waitLastStep) {
    return (
      <div className="sim-page flex items-center justify-center px-4 py-10 sm:px-6">
        <ReportLoading
          title={generating || requestingNew ? 'Gerando seu relatório' : 'Carregando seu relatório'}
          onLastStep={markLastStep}
        />
      </div>
    )
  }

  const report = query.data
  // "Abrir a simulação" leva à revisão mais nova coberta: a `url` já vem pronta da API, sem
  // supor ordem no array nem remontar o caminho aqui.
  const newest = newestRow(report)
  const simulationUrl = newest?.url ?? '/simulacoes'
  const derived = report.derivados
  const header = report.cabecalho
  const rows = rowsById(report.por_revisao)

  return (
    <div className="sim-page">
      <main className="mx-auto flex max-w-screen-2xl flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <ReportHeading
          report={report}
          simulationUrl={simulationUrl}
          onRequestNewReport={requestNewReport}
          requestingNewReport={createReport.isPending}
        />
        {createReport.isError && (
          <p role="alert" className="text-sm text-danger">
            Não foi possível pedir um relatório novo: {createReport.error.message}
          </p>
        )}
        <NewRevisionsNotice report={report} />

        {newest && <ResultHero row={newest} header={header} derived={derived} />}
        {header && <CurtailmentContext header={header} />}
        <ModelReading report={report} />
        <RevisionComparison report={report} />

        {(header || derived) && (
          <section
            aria-labelledby="detalhes"
            className="flex flex-col gap-4 border-t border-(--sim-border) pt-8"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2
                  id="detalhes"
                  className="sim-display text-xl font-semibold text-(--sim-brand-ink)"
                >
                  Detalhes
                </h2>
                <p className="mt-1 text-sm text-(--sim-muted-foreground)">
                  Contexto da restrição, o que foi testado e cada revisão.
                </p>
              </div>
            </div>

            {header && (
              <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
                <ConstraintDetails header={header} />
                <ExplorationTrail
                  steps={report.trilha}
                  rows={rows}
                  nextRevisionUrl={
                    newest ? newRevisionUrl(header.restricao_id, newest.revisao_id) : undefined
                  }
                />
              </div>
            )}
            {derived && <ConfigMatrix derived={derived} />}
          </section>
        )}
      </main>
    </div>
  )
}
