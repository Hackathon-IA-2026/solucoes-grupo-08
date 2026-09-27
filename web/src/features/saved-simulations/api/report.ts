import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type {
  SchemaFalhaDeVerificacao,
  SchemaItemFixo,
  SchemaLinhaDaRevisao,
  SchemaPassoDaTrilha,
  SchemaPremissaExposta,
  SchemaRelatorio,
  SchemaRelatorioCriado,
  SchemaRelatorioNaLista,
  SchemaSensibilidade,
} from '@/api/gerado/tipos'
import type { MutationConfig, QueryConfig } from '@/lib/react-query'

export type Report = SchemaRelatorio
export type ReportCreated = SchemaRelatorioCriado
export type ReportListItem = SchemaRelatorioNaLista
export type ReportState = Report['estado']
export type ReportHeader = NonNullable<Report['cabecalho']>
export type TrailStep = SchemaPassoDaTrilha
export type ProseSection = SchemaFalhaDeVerificacao['secao']
export type Derived = NonNullable<Report['derivados']>
export type ExposedPremise = SchemaPremissaExposta
export type RevisionRow = SchemaLinhaDaRevisao
export type Sensitivity = SchemaSensibilidade
export type FixedItem = SchemaItemFixo

// A chave de `Derivados.ordenacoes` é índice livre no tipo gerado (o contrato a restringe por
// `propertyNames.enum`, que o openapi-typescript não traz para o TypeScript); mantida à mão.
export type RankingKey = 'vpl' | 'fracao_recuperada' | 'payback_descontado' | 'custo_por_mwh'

/** O que a lista de relatórios manda na navegação ao abrir um: se ele já saiu de `gerando`. */
export type ReportOpenState = { generated?: boolean }

export const getReport = (simulationId: number, reportId: number): Promise<Report> => {
  return httpClient.get(`/simulacoes/${simulationId}/relatorios/${reportId}`)
}

export const getReportQueryOptions = (simulationId: number, reportId: number) => {
  return queryOptions({
    queryKey: ['simulacoes', simulationId, 'relatorios', reportId],
    queryFn: () => getReport(simulationId, reportId),
    enabled: Number.isFinite(simulationId) && Number.isFinite(reportId),
    // Relatório finalizado (`pronto`, `barrado`, `falhou`): uma chamada ao abrir e nada mais.
    // Em `gerando` a tarefa de fundo ainda não terminou, então relê sozinho até sair desse estado
    // e para. Só enquanto gera, e também com a aba em segundo plano: sem isso o React Query
    // pausa a leitura quando a aba perde o foco e a tela fica presa em `gerando`.
    refetchInterval: (query) => (query.state.data?.estado === 'gerando' ? 5_000 : false),
    refetchIntervalInBackground: true,
  })
}

type UseReportOptions = {
  simulationId: number
  reportId: number
  queryConfig?: QueryConfig<typeof getReportQueryOptions>
}

export const useReport = ({ simulationId, reportId, queryConfig }: UseReportOptions) => {
  return useQuery({
    ...getReportQueryOptions(simulationId, reportId),
    ...queryConfig,
  })
}

/** Cria em `gerando`, sobre as revisões que existem agora. A geração corre em tarefa de fundo. */
export const createReport = (simulationId: number): Promise<ReportCreated> => {
  return httpClient.post(`/simulacoes/${simulationId}/relatorios`)
}

// `simulationId` já vem do hook, então `mutate()` do chamador não leva argumento: a assinatura
// de `createReport` (que leva `simulationId`) não serve de molde para `MutationConfig` aqui.
type UseCreateReportOptions = {
  simulationId: number
  mutationConfig?: MutationConfig<() => Promise<ReportCreated>>
}

export const useCreateReport = ({ simulationId, mutationConfig }: UseCreateReportOptions) => {
  const queryClient = useQueryClient()
  const { onSuccess, ...rest } = mutationConfig ?? {}

  return useMutation({
    mutationFn: () => createReport(simulationId),
    onSuccess: (...args) => {
      void queryClient.invalidateQueries({ queryKey: ['simulacoes', simulationId, 'relatorios'] })
      onSuccess?.(...args)
    },
    ...rest,
  })
}

/** Os relatórios da simulação, do mais novo para o mais velho. Lista vazia: ainda não há nenhum. */
export const listReports = (
  simulationId: number,
  signal?: AbortSignal,
): Promise<ReportListItem[]> => {
  return httpClient.get(`/simulacoes/${simulationId}/relatorios`, { signal })
}

export const listReportsQueryOptions = (simulationId: number) => {
  return queryOptions({
    queryKey: ['simulacoes', simulationId, 'relatorios'],
    queryFn: ({ signal }) => listReports(simulationId, signal),
    enabled: Number.isFinite(simulationId),
    // Mesmo critério do relatório: só enquanto algum ainda está `gerando` a lista se relê, para o
    // estado dele sair de "Gerando" sozinho. Parada a lista, nenhuma chamada além da primeira.
    refetchInterval: (query) =>
      query.state.data?.some((report) => report.estado === 'gerando') ? 5_000 : false,
    refetchIntervalInBackground: true,
  })
}

export const useReports = ({
  simulationId,
  enabled,
}: {
  simulationId: number
  enabled?: boolean
}) => {
  const options = listReportsQueryOptions(simulationId)
  return useQuery({ ...options, enabled: options.enabled && (enabled ?? true) })
}
