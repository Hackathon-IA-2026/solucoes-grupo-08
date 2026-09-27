import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaRevisaoCompleta } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'

export type FullRevision = SchemaRevisaoCompleta
export type Result = FullRevision['resultado']
export type Configuration = FullRevision['configuracao']
export type SiblingRevision = FullRevision['revisoes'][number]

export const getSimulation = (revisionId: number): Promise<FullRevision> => {
  return httpClient.get(`/simulacoes/${revisionId}`)
}

export const getSimulationQueryOptions = (revisionId: number) => {
  return queryOptions({
    queryKey: ['simulacoes', 'revisao', revisionId],
    queryFn: () => getSimulation(revisionId),
    enabled: Number.isFinite(revisionId),
  })
}

type UseSimulationOptions = {
  revisionId: number
  queryConfig?: QueryConfig<typeof getSimulationQueryOptions>
}

export const useSimulation = ({ revisionId, queryConfig }: UseSimulationOptions) => {
  return useQuery({
    ...getSimulationQueryOptions(revisionId),
    ...queryConfig,
  })
}
