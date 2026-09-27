import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaRestricaoDetalhada } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'
import type { Source } from './get-restrictions'
import { truncateText } from '@/utils/format'

export type DetailedRestriction = SchemaRestricaoDetalhada
export type ScreenEquipment = DetailedRestriction['equipamentos'][number]

export type GetRestrictionParams = {
  restrictionId: string
  source?: Source
}

export const getRestriction = ({
  restrictionId,
  source,
}: GetRestrictionParams): Promise<DetailedRestriction> => {
  return httpClient.get(`/restricoes/${restrictionId}`, { params: { fonte: source } })
}

export const getRestrictionQueryOptions = ({ restrictionId, source }: GetRestrictionParams) => {
  return queryOptions({
    queryKey: ['restricoes', restrictionId, source ?? 'eolica'],
    queryFn: () => getRestriction({ restrictionId, source }),
    enabled: Boolean(restrictionId),
  })
}

type UseRestrictionOptions = GetRestrictionParams & {
  queryConfig?: QueryConfig<typeof getRestrictionQueryOptions>
}

export const useRestriction = ({ restrictionId, source, queryConfig }: UseRestrictionOptions) => {
  return useQuery({
    ...getRestrictionQueryOptions({ restrictionId, source }),
    ...queryConfig,
  })
}

/** O nome curto da restrição para títulos e trilhas; sem ele, o texto do ONS encurtado. */
export const restrictionName = (restriction: { nome_curto?: string | null; texto: string }) =>
  restriction.nome_curto ?? truncateText(restriction.texto, 60)
