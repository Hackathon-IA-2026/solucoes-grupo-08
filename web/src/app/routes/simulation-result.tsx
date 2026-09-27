import { Link, useParams } from 'react-router'
import { useRestriction } from '@/features/restrictions/api/get-restriction'
import { useSimulation } from '@/features/saved-simulations/api/get-simulation'
import { CashFlowTable } from '@/features/saved-simulations/components/result/cash-flow-table'
import { ResultCharts } from '@/features/saved-simulations/components/result/result-charts'
import { ResultHeader } from '@/features/saved-simulations/components/result/result-header'
import {
  FinancialSummary,
  TechnicalKpis,
} from '@/features/saved-simulations/components/result/result-kpis'
import { RevisionConfig } from '@/features/saved-simulations/components/result/revision-config'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

/** Uma revisão salva: energia recuperada, financeiro, premissas, avisos e configuração. */
export default function SimulationResult() {
  const { revisaoId: revisionId } = useParams()
  const query = useSimulation({ revisionId: Number(revisionId) })
  // O nome da linha e o texto da restrição vêm do cadastro; a revisão guarda só o código e o id.
  const restriction = useRestriction({ restrictionId: query.data?.restricao_id ?? '' })

  if (query.isPending) {
    return (
      <div className="mx-auto flex max-w-360 justify-center px-6 py-16">
        <Spinner />
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="mx-auto max-w-360 px-6 py-8">
        <p className="text-sm text-warning">
          Não foi possível carregar a revisão "{revisionId}": {query.error.message}
        </p>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/simulacoes">Voltar para Simulações</Link>
        </Button>
      </div>
    )
  }

  const revision = query.data
  const { bateria: battery, equipamento: equipment } = revision.configuracao
  const lineName = restriction.data?.equipamentos.find(
    (row) => row.cod_equipamento === equipment?.cod_equipamento,
  )?.nome

  const position = revision.revisoes.find((sibling) => sibling.id === revision.id)?.posicao ?? 1

  return (
    <div className="sim-page">
      <ResultHeader revision={revision} restrictionText={restriction.data?.texto} />

      <div className="mx-auto max-w-screen-2xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
        <section>
          <div className="sim-heading">
            <div>
              <h2>Resultado operacional</h2>
              <p>Energia afetada e recuperação estimada pela intervenção.</p>
            </div>
            <span>Unidade principal: MWh</span>
          </div>
          <TechnicalKpis result={revision.resultado} configuration={revision.configuracao} />
        </section>

        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-12">
          <ResultCharts
            result={revision.resultado}
            batteryCapacityMwh={battery ? battery.capacidade_mwh : null}
          />
          <FinancialSummary
            result={revision.resultado}
            configuration={revision.configuracao}
            position={position}
          />
        </div>

        <CashFlowTable result={revision.resultado} />

        <RevisionConfig
          configuration={revision.configuracao}
          lineName={lineName ?? undefined}
          position={position}
        />
      </div>
    </div>
  )
}
