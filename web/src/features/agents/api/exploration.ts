import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, httpClient } from '@/api/client'
import type { components } from '@/api/gerado/tipos'

export type Task = components['schemas']['TarefaNaTela']
export type TaskState = Task['estado']
export type Counts = components['schemas']['Contagem']
export type RecordedEvent = components['schemas']['EventoGravado']
export type ExplorationEvent = RecordedEvent['evento']
export type Summary = components['schemas']['ResumoDaRevisao']
export type PlannedVariation = components['schemas']['VariacaoPlanejada']
export type Lever = components['schemas']['AlavancaFisica']
type TaskRequestSchema = components['schemas']['PedidoDeTarefa']
/** O `teto` tem padrão na API; o gerador o marca como obrigatório só por ter padrão. */
export type TaskRequest = Omit<TaskRequestSchema, 'teto'> & Partial<Pick<TaskRequestSchema, 'teto'>>
type TaskConflict = components['schemas']['DetalheDoConflito']
export type ExplorationSummary = components['schemas']['ResumoDaExploracao']
export type AllowedRange = components['schemas']['FaixaPermitida']
export type Premise = components['schemas']['Premissa']

/** Um por tipo do contrato: o `EventSource` só entrega pelo nome do `event:`, sem `onmessage`. */
export const EVENT_TYPES = [
  'decidindo_rodada',
  'rodada_decidida',
  'variacao_iniciada',
  'variacao_passo',
  'revisao_pronta',
  'variacao_recusada',
  'relatorio_pedido',
  'relatorio_pronto',
  'tarefa_terminada',
] as const satisfies readonly ExplorationEvent['tipo'][]

export const getTasks = (simulationId: number): Promise<Task[]> =>
  httpClient.get(`/simulacoes/${simulationId}/tarefas`)

export const getTask = (taskId: number): Promise<Task> => httpClient.get(`/tarefas/${taskId}`)

export const tasksQueryOptions = (simulationId: number) =>
  queryOptions({
    queryKey: ['simulacoes', simulationId, 'tarefas'],
    queryFn: () => getTasks(simulationId),
    enabled: Number.isFinite(simulationId),
  })

export const taskQueryOptions = (taskId: number) =>
  queryOptions({
    queryKey: ['tarefas', taskId],
    queryFn: () => getTask(taskId),
    enabled: Number.isFinite(taskId),
  })

/** As explorações da simulação, da mais nova para a mais velha. */
export const useTasks = (simulationId: number, options: { enabled?: boolean } = {}) =>
  useQuery({ ...tasksQueryOptions(simulationId), ...options })

export const useTask = (taskId: number) => useQuery(taskQueryOptions(taskId))

export const createTask = (simulationId: number, request: TaskRequest): Promise<Task> =>
  httpClient.post(`/simulacoes/${simulationId}/tarefas`, request)

/** Cria a exploração da simulação. A lista de explorações dela fica velha e é relida. */
export const useCreateTask = (simulationId: number) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: TaskRequest) => createTask(simulationId, request),
    onSuccess: (task) => {
      queryClient.setQueryData(taskQueryOptions(task.id).queryKey, task)
      void queryClient.invalidateQueries({ queryKey: tasksQueryOptions(simulationId).queryKey })
    },
  })
}

type SummaryParams = { revisionId?: number; levers?: Lever[] }

export const getExplorationSummary = (
  simulationId: number,
  { revisionId, levers }: SummaryParams,
): Promise<ExplorationSummary> =>
  httpClient.get(`/simulacoes/${simulationId}/exploracao`, {
    params: { revisao_partida_id: revisionId, alavancas: levers },
    // A API lê lista como a chave repetida (`alavancas=a&alavancas=b`), sem colchetes.
    paramsSerializer: { indexes: null },
  })

/**
 * O que se confirma antes de criar a exploração: de onde parte, o que pode variar e o que fica
 * fixo. Sem revisão, a API parte da mais nova; sem alavancas, de todas as da modalidade.
 */
export const useExplorationSummary = (
  simulationId: number,
  params: SummaryParams,
  enabled = true,
) =>
  useQuery({
    queryKey: [
      'simulacoes',
      simulationId,
      'exploracao',
      params.revisionId ?? null,
      params.levers ?? null,
    ],
    queryFn: () => getExplorationSummary(simulationId, params),
    enabled: enabled && Number.isFinite(simulationId),
  })

/** A exploração que já está rodando, quando a API recusa uma segunda (`409`). */
export function runningTaskId(error: unknown): number | undefined {
  if (!(error instanceof ApiError) || error.status !== 409) return undefined
  const detail = error.detail as Partial<TaskConflict> | undefined
  return typeof detail?.tarefa_id === 'number' ? detail.tarefa_id : undefined
}

/** URL do streaming: absoluta na base da API, porque o `EventSource` não passa pelo axios. */
export const eventsUrl = (taskId: number) =>
  `${httpClient.defaults.baseURL ?? ''}/tarefas/${taskId}/eventos`
