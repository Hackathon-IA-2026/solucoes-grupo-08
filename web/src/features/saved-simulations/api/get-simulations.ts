import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaSimulacaoNaLista } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'

export type SimulationListItem = SchemaSimulacaoNaLista
export type RevisionListItem = SimulationListItem['revisoes'][number]

export type GetSimulationsParams = {
  /** Só as simulações desta restrição. Sem ele, todas. */
  restrictionId?: string
}

export const getSimulations = ({ restrictionId }: GetSimulationsParams = {}): Promise<
  SimulationListItem[]
> => {
  return httpClient.get('/simulacoes', { params: { restricao_id: restrictionId } })
}

export const getSimulationsQueryOptions = (params: GetSimulationsParams = {}) => {
  return queryOptions({
    queryKey: ['simulacoes', params.restrictionId ?? null],
    queryFn: () => getSimulations(params),
  })
}

type UseSimulationsOptions = GetSimulationsParams & {
  queryConfig?: QueryConfig<typeof getSimulationsQueryOptions>
}

export const useSimulations = ({ restrictionId, queryConfig }: UseSimulationsOptions = {}) => {
  return useQuery({
    ...getSimulationsQueryOptions({ restrictionId }),
    ...queryConfig,
  })
}
