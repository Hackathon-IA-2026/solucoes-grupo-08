import { FormProvider } from 'react-hook-form'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { RestrictionNotMeasured } from '@/features/restrictions/components/restriction-not-measured'
import { restrictionName, useRestriction } from '@/features/restrictions/api/get-restriction'
import { CreationModeDialog } from '@/features/simulations/components/creation-mode-dialog'
import { Breadcrumbs } from '@/components/layout/breadcrumbs'
import { useSimulationFlow } from '@/features/simulations/form/use-simulation-flow'
import { StepIdentification } from '@/features/simulations/components/step-identification'
import { StepFinancial } from '@/features/simulations/components/step-financial'
import { StepModality } from '@/features/simulations/components/step-modality'
import { StepPeriod } from '@/features/simulations/components/step-period'
import { StepTechnical } from '@/features/simulations/components/step-technical'
import { SimulationStepsNav } from '@/features/simulations/components/simulation-steps-nav'
import { SimulationSummaryBar } from '@/features/simulations/components/simulation-summary-bar'
import { useSimulation } from '@/features/saved-simulations/api/get-simulation'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

export default function SimulationNew() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const restrictionQuery = useRestriction({ restrictionId: id ?? '', source: 'eolica' })

  // "Criar revisão": ?revisar=<id> traz aquela revisão salva e o formulário nasce cópia dela.
  const revisionIdParam = searchParams.get('revisar')
  const revisionId = revisionIdParam === null ? Number.NaN : Number(revisionIdParam)
  const wantsRevision = revisionIdParam !== null && Number.isFinite(revisionId)
  const revisionQuery = useSimulation({ revisionId })

  const flow = useSimulationFlow(
    restrictionQuery.data,
    wantsRevision ? revisionQuery.data : undefined,
  )

  if (restrictionQuery.isPending || (wantsRevision && revisionQuery.isPending)) {
    return (
      <div className="sim-page">
        <div className="flex justify-center px-6 py-16">
          <Spinner />
        </div>
      </div>
    )
  }

  if (restrictionQuery.isError || (wantsRevision && revisionQuery.isError)) {
    return (
      <div className="sim-page">
        <div className="mx-auto max-w-screen-2xl px-4 py-8 sm:px-6 lg:px-8">
          <p className="text-sm text-warning">
            {restrictionQuery.isError
              ? `Não foi possível carregar a restrição "${id}": ${restrictionQuery.error.message}`
              : `Não foi possível carregar a revisão "${revisionIdParam}": ${revisionQuery.error?.message}`}
          </p>
          <Button asChild variant="outline" className="mt-4">
            <Link to="/">Voltar para Restrições</Link>
          </Button>
        </div>
      </div>
    )
  }

  const restriction = restrictionQuery.data

  return (
    <div className="sim-page">
      <SimulationSummaryBar restriction={restriction} />
      <div className="mx-auto max-w-screen-2xl px-4 pt-5 sm:px-6 lg:px-8">
        <Breadcrumbs
          items={
            wantsRevision && revisionQuery.data
              ? [
                  { label: 'Simulações', to: '/simulacoes' },
                  { label: revisionQuery.data.nome, to: `/simulacoes/${revisionQuery.data.id}` },
                  { label: 'Nova revisão' },
                ]
              : [
                  { label: 'Restrições', to: '/' },
                  { label: restrictionName(restriction), to: `/restricoes/${restriction.id}` },
                  { label: 'Nova simulação' },
                ]
          }
        />
      </div>

      <div className="mx-auto flex max-w-screen-2xl flex-col gap-6 px-4 py-6 sm:px-6 lg:flex-row lg:gap-8 lg:px-8 lg:py-8">
        <SimulationStepsNav
          currentStep={flow.step}
          simulationName={flow.name}
          onStepChange={flow.goToStep}
        />

        <div className="min-w-0 flex-1">
          <RestrictionNotMeasured item={restriction} className="mb-4" />
          {/* Um formulário só para as cinco etapas: o RHF guarda os valores de todas. */}
          <FormProvider {...flow.form}>
            <form onSubmit={flow.onFormSubmit} noValidate>
              {flow.step === 1 ? (
                <StepIdentification
                  restriction={restriction}
                  canSwapRestriction={!wantsRevision}
                  onCancel={() => navigate(`/restricoes/${restriction.id}`)}
                  onContinue={flow.goNext}
                />
              ) : flow.step === 2 ? (
                <StepPeriod onBack={flow.goBack} onContinue={flow.goNext} />
              ) : flow.step === 3 ? (
                <StepModality onBack={flow.goBack} onContinue={flow.goNext} />
              ) : flow.step === 4 ? (
                <StepTechnical
                  restriction={restriction}
                  modality={flow.modality}
                  onBack={flow.goBack}
                  onContinue={flow.goNext}
                />
              ) : (
                <StepFinancial
                  premises={flow.premises}
                  isSubmitting={flow.isSubmitting}
                  onBack={flow.goBack}
                />
              )}
            </form>
          </FormProvider>
          <CreationModeDialog
            open={flow.creationOpen}
            onOpenChange={flow.setCreationOpen}
            onConfirm={(choice) => void flow.confirmCreation(choice)}
            creating={flow.creating}
            confirmDisabled={flow.creationError?.savedRevisionId != null}
            error={
              flow.creationError && (
                <>
                  {flow.creationError.message}
                  {flow.creationError.savedRevisionId != null && (
                    <>
                      {' '}
                      <Link
                        to={`/simulacoes/${flow.creationError.savedRevisionId}`}
                        className="font-semibold underline"
                      >
                        Abrir a simulação criada
                      </Link>
                    </>
                  )}
                </>
              )
            }
          />
        </div>
      </div>
    </div>
  )
}
