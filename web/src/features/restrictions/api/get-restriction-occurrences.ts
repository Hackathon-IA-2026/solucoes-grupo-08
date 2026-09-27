import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaOcorrenciasNaTela } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'
import type { Source } from './get-restrictions'

export type RestrictionOccurrences = SchemaOcorrenciasNaTela
export type Occurrence = RestrictionOccurrences['itens'][number]

export type GetRestrictionOccurrencesParams = {
  restrictionId: string
  source?: Source
}

/** Episódios de corte da restrição no snapshot ativo, da maior energia para a menor. */
export const getRestrictionOccurrences = ({
  restrictionId,
  source,
}: GetRestrictionOccurrencesParams): Promise<RestrictionOccurrences> => {
  return httpClient.get(`/restricoes/${restrictionId}/ocorrencias`, {
    params: { fonte: source },
  })
}

export const getRestrictionOccurrencesQueryOptions = ({
  restrictionId,
  source,
}: GetRestrictionOccurrencesParams) => {
  return queryOptions({
    queryKey: ['restricoes', restrictionId, 'ocorrencias', source ?? 'eolica'],
    queryFn: () => getRestrictionOccurrences({ restrictionId, source }),
    enabled: Boolean(restrictionId),
  })
}

type UseRestrictionOccurrencesOptions = GetRestrictionOccurrencesParams & {
  queryConfig?: QueryConfig<typeof getRestrictionOccurrencesQueryOptions>
}

export const useRestrictionOccurrences = ({
  restrictionId,
  source,
  queryConfig,
}: UseRestrictionOccurrencesOptions) => {
  return useQuery({
    ...getRestrictionOccurrencesQueryOptions({ restrictionId, source }),
    ...queryConfig,
  })
}
