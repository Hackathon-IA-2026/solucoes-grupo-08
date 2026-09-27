import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaSerieNaTela, SchemaAgregacao } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'
import type { Source } from './get-restrictions'

export type Aggregation = SchemaAgregacao
export type RestrictionSeries = SchemaSerieNaTela

export type GetRestrictionSeriesParams = {
  restrictionId: string
  source?: Source
  aggregation?: Aggregation
}

export const getRestrictionSeries = ({
  restrictionId,
  source,
  aggregation,
}: GetRestrictionSeriesParams): Promise<RestrictionSeries> => {
  return httpClient.get(`/restricoes/${restrictionId}/serie`, {
    params: { fonte: source, agregacao: aggregation },
  })
}

export const getRestrictionSeriesQueryOptions = (params: GetRestrictionSeriesParams) => {
  return queryOptions({
    queryKey: [
      'restricoes',
      params.restrictionId,
      'serie',
      params.source ?? 'eolica',
      params.aggregation ?? 'meia_hora',
    ],
    queryFn: () => getRestrictionSeries(params),
    enabled: Boolean(params.restrictionId),
  })
}

type UseRestrictionSeriesOptions = GetRestrictionSeriesParams & {
  queryConfig?: QueryConfig<typeof getRestrictionSeriesQueryOptions>
}

export const useRestrictionSeries = ({
  restrictionId,
  source,
  aggregation,
  queryConfig,
}: UseRestrictionSeriesOptions) => {
  return useQuery({
    ...getRestrictionSeriesQueryOptions({ restrictionId, source, aggregation }),
    ...queryConfig,
  })
}
