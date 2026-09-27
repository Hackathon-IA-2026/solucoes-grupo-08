import { queryOptions, useQuery } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaSnapshotAtivo } from '@/api/gerado/tipos'
import type { QueryConfig } from '@/lib/react-query'

export type Snapshot = SchemaSnapshotAtivo

export const getSnapshot = (): Promise<Snapshot> => {
  return httpClient.get('/snapshot')
}

export const getSnapshotQueryOptions = () => {
  return queryOptions({
    queryKey: ['snapshot'],
    queryFn: getSnapshot,
  })
}

type UseSnapshotOptions = {
  queryConfig?: QueryConfig<typeof getSnapshotQueryOptions>
}

export const useSnapshot = ({ queryConfig }: UseSnapshotOptions = {}) => {
  return useQuery({
    ...getSnapshotQueryOptions(),
    ...queryConfig,
  })
}
