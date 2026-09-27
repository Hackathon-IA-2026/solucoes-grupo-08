import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaCenario, SchemaModalidade, SchemaPremissasNaTela } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'

export type Scenario = SchemaCenario
export type ScreenPremises = SchemaPremissasNaTela

export type GetPremisesParams = {
  scenario?: Scenario
  modality?: SchemaModalidade
}

export const getPremises = (params: GetPremisesParams = {}): Promise<ScreenPremises> => {
  // Os nomes da query string são os do contrato.
  return httpClient.get('/premissas', {
    params: { cenario: params.scenario, modalidade: params.modality },
  })
}

export const getPremisesQueryOptions = (params: GetPremisesParams = {}) => {
  return queryOptions({
    queryKey: ['premissas', params.scenario ?? 'referencia', params.modality ?? null],
    queryFn: () => getPremises(params),
  })
}

type UsePremisesOptions = GetPremisesParams & {
  queryConfig?: QueryConfig<typeof getPremisesQueryOptions>
}

export const usePremises = ({ scenario, modality, queryConfig }: UsePremisesOptions = {}) => {
  return useQuery({
    ...getPremisesQueryOptions({ scenario, modality }),
    ...queryConfig,
  })
}
