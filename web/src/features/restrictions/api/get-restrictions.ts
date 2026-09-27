import { truncateText } from '@/utils/format'
import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaListaDeRestricoes, SchemaFonte } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'

export type Source = SchemaFonte
export type RestrictionList = SchemaListaDeRestricoes
export type RestrictionListItem = RestrictionList['itens'][number]
export type RestrictionsSummary = RestrictionList['resumo']

export const sourceLabels: Record<Source, string> = {
  eolica: 'eólica',
  solar: 'solar',
  ambas: 'ambas',
}

/** Busca da lista: nome curto, texto original do ONS ou subestação, sem diferenciar caixa. */
export function matchesSearch(item: RestrictionListItem, search: string) {
  const haystack =
    `${item.nome_curto ?? ''} ${item.texto} ${item.subestacoes.join(' ')}`.toLowerCase()
  return haystack.includes(search.trim().toLowerCase())
}

export type GetRestrictionsParams = {
  source?: Source
}

export const getRestrictions = (params: GetRestrictionsParams = {}): Promise<RestrictionList> => {
  return httpClient.get('/restricoes', { params: { fonte: params.source } })
}

export const getRestrictionsQueryOptions = (params: GetRestrictionsParams = {}) => {
  return queryOptions({
    queryKey: ['restricoes', params.source ?? 'eolica'],
    queryFn: () => getRestrictions(params),
  })
}

type UseRestrictionsOptions = GetRestrictionsParams & {
  queryConfig?: QueryConfig<typeof getRestrictionsQueryOptions>
}

export const useRestrictions = ({ source, queryConfig }: UseRestrictionsOptions = {}) => {
  return useQuery({
    ...getRestrictionsQueryOptions({ source }),
    ...queryConfig,
  })
}

/** O nome curto quando a API o traz; senão o texto do ONS, truncado. */
export function displayName(item: RestrictionListItem, maxLength: number) {
  return item.nome_curto ?? truncateText(item.texto, maxLength)
}
