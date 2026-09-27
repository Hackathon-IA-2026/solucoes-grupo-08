import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { get, useForm, useWatch, type FieldErrors } from 'react-hook-form'
import { useNavigate } from 'react-router'
import {
  visibleFields,
  fieldForPremise,
  STEPS,
  FIRST_STEP,
  LAST_STEP,
  type Step,
} from './constants'
import { buildRequest } from './build-request'
import { runCreation, type CreationChoice, type CreationError } from './creation-mode'
import { formDataFromRevision } from './from-revision'
import { formSchema, initialValues, type SimulationFormData } from './schema'
import { usePremises } from '../api/get-premises'
import { useSaveSimulation } from '../api/save-simulation'
import { createTask } from '@/features/agents/api/exploration'
import type { DetailedRestriction } from '@/features/restrictions/api/get-restriction'
import type { FullRevision } from '@/features/saved-simulations/api/get-simulation'

/** O valor da premissa como número do formulário. Texto e booleano não são valor de campo. */
function asNumber(value: string | number | boolean): number | undefined {
  const number = typeof value === 'string' && value.trim() !== '' ? Number(value) : value
  return typeof number === 'number' && Number.isFinite(number) ? number : undefined
}

/** A primeira etapa (em ordem) que tem algum erro. */
function firstStepWithError(errors: FieldErrors<SimulationFormData>): Step | undefined {
  return STEPS.find((step) => `step${step}` in errors)
}

/**
 * O fluxo da Nova simulação: um único formulário para as cinco etapas, mais a etapa atual.
 *
 * Com `revisionToClone`, a tela é "Criar revisão": o formulário nasce com os valores daquela
 * revisão salva (`GET /simulacoes/{revisao_id}`), e o envio manda `simulacao_id` em vez de
 * `restricao_id` — vira revisão nova da mesma simulação, não uma simulação nova.
 *
 * O React Hook Form guarda todos os valores, inclusive os das etapas que não estão na tela, então
 * voltar e avançar não perde nada. O único estado próprio daqui é de navegação e de envio.
 */
export function useSimulationFlow(
  restriction: DetailedRestriction | undefined,
  revisionToClone?: FullRevision,
) {
  const form = useForm<SimulationFormData>({
    resolver: zodResolver(formSchema),
    mode: 'onChange',
    defaultValues: initialValues,
  })
  const [step, setStep] = useState<Step>(FIRST_STEP)
  const [maxStep, setMaxStep] = useState<Step>(FIRST_STEP)
  // Validado, o formulário espera aqui a escolha do modal de finalização (normal ou com agentes).
  const [pendingData, setPendingData] = useState<SimulationFormData | null>(null)
  const [creationOpen, setCreationOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [creationError, setCreationError] = useState<CreationError | null>(null)
  const navigate = useNavigate()
  const saveMutation = useSaveSimulation()

  // A revisão a clonar chega depois do primeiro render (é dado de rota): semeia o formulário
  // inteiro uma vez, e só uma vez — reset novo apagaria o que o usuário já editou. Os dados já
  // são de uma revisão salva e válida, então a barra lateral libera as cinco etapas de uma vez,
  // sem obrigar a clicar Continuar em cada uma para só então poder pular para a etapa que importa.
  // Abre direto na etapa 2: nome e pergunta da etapa 1 são ignorados pela API ao revisar.
  const seededFromRevision = useRef(false)
  const { reset } = form
  useEffect(() => {
    if (!revisionToClone || seededFromRevision.current) return
    seededFromRevision.current = true
    reset(formDataFromRevision(revisionToClone))
    setMaxStep(LAST_STEP)
    setStep(2)
  }, [revisionToClone, reset])

  // Ler daqui inscreve o componente nas mudanças: são os dois campos que mudam o que se busca e o
  // que se mostra. Os outros valores ficam no formulário, sem re-render a cada tecla.
  const modality = useWatch({ control: form.control, name: 'step3.modalidade' })
  const scenario = useWatch({ control: form.control, name: 'step5.cenario' })
  const name = useWatch({ control: form.control, name: 'step1.nome' })
  const { dirtyFields, isSubmitting } = form.formState

  const premisesQuery = usePremises({ scenario, modality })
  const premises = premisesQuery.data

  // Valor inicial do cenário (`GET /premissas`), só nos campos que o usuário ainda não mexeu.
  // Mudar de cenário ou de modalidade atualiza esses e deixa em paz o que foi digitado.
  const touched = useRef(dirtyFields)
  useEffect(() => {
    touched.current = dirtyFields
  })
  const { setValue } = form
  useEffect(() => {
    // Clonando uma revisão, os campos já têm o que ela de fato calculou: o catálogo de hoje não
    // sobrescreve isso, mesmo que o preço ou a taxa padrão tenham mudado desde então.
    if (revisionToClone) return
    for (const { campo: field, premissa: premise } of premises?.valores_iniciais ?? []) {
      const path = fieldForPremise(field)
      const value = asNumber(premise.valor)
      if (!path || value === undefined || get(touched.current, path)) continue
      setValue(path, value, { shouldDirty: false, shouldValidate: false })
    }
  }, [premises, setValue, revisionToClone])

  // Subestação e linha são da restrição. Trocar de restrição ("Trocar de restrição" na etapa 1)
  // mantém o formulário, então a escolha que não existe na nova volta a vazio. Com uma opção só,
  // ela já vem escolhida: uma subestação, uma linha.
  useEffect(() => {
    if (!restriction) return
    const substations = restriction.subestacoes
    const lines = restriction.equipamentos.map((row) => row.cod_equipamento)
    const substation = form.getValues('step4.bateria.subestacao')
    const line = form.getValues('step4.equipamento.cod_equipamento')

    if (substation && !substations.includes(substation)) {
      setValue('step4.bateria.subestacao', '')
    }
    if (line && !lines.includes(line)) {
      setValue('step4.equipamento.cod_equipamento', '')
    }
    if (substations.length === 1 && !form.getValues('step4.bateria.subestacao')) {
      setValue('step4.bateria.subestacao', substations[0])
    }
    if (lines.length === 1 && !form.getValues('step4.equipamento.cod_equipamento')) {
      setValue('step4.equipamento.cod_equipamento', lines[0])
    }
  }, [restriction, setValue, form])

  function goTo(target: Step) {
    setStep(target)
    setMaxStep((current) => Math.max(current, target) as Step)
  }

  /** Continuar: valida só os campos da etapa atual e só então avança. */
  async function goNext() {
    if (step >= LAST_STEP) return
    const fields = visibleFields(step, form.getValues('step3.modalidade'))
    const isValid = await form.trigger(fields, { shouldFocus: true })
    if (isValid) goTo((step + 1) as Step)
  }

  /** Voltar: sem validar e sem tocar nos dados. */
  function goBack() {
    if (step > FIRST_STEP) setStep((step - 1) as Step)
  }

  /** Pela sidebar: para trás e para etapas já visitadas, nunca pulando etapa sem validar. */
  function goToStep(target: Step) {
    if (target <= maxStep) setStep(target)
  }

  /** Formulário inteiro válido: em vez de salvar já, pergunta como criar. */
  function submitData(data: SimulationFormData) {
    setPendingData(data)
    setCreationError(null)
    setCreationOpen(true)
  }

  /**
   * A confirmação do modal: calcula e salva na API e leva ao resultado. Com agentes, a exploração
   * começa em seguida a partir da revisão salva, com a instrução como pedido, e a tela vai para o
   * acompanhamento dela.
   */
  async function confirmCreation(choice: CreationChoice) {
    if (!restriction || !pendingData) return
    setCreating(true)
    setCreationError(null)
    const origin = revisionToClone
      ? ({ mode: 'revise', simulationId: revisionToClone.simulacao_id } as const)
      : ({ mode: 'create', restrictionId: restriction.id } as const)
    const outcome = await runCreation(choice, {
      save: () => saveMutation.mutateAsync(buildRequest(origin, pendingData)),
      startExploration: createTask,
    })
    if ('to' in outcome) return navigate(outcome.to)
    setCreating(false)
    setCreationError(outcome.error)
  }

  /** Envio com erro de validação: leva para a primeira etapa com problema, e não deixa passar. */
  function onInvalid(errors: FieldErrors<SimulationFormData>) {
    const withError = firstStepWithError(errors)
    if (withError) setStep(withError)
  }

  /**
   * O submit do <form>. Fora da última etapa, Enter num campo faz o mesmo que Continuar; só na
   * última o formulário inteiro é validado e enviado.
   */
  const onFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    if (step === LAST_STEP) return form.handleSubmit(submitData, onInvalid)(event)
    event.preventDefault()
    return goNext()
  }

  return {
    form,
    step,
    modality,
    name,
    premises,
    isSubmitting,
    creationOpen,
    setCreationOpen,
    creating,
    creationError,
    confirmCreation,
    goNext,
    goBack,
    goToStep,
    onFormSubmit,
  }
}
