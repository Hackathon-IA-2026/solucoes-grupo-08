import { SearchX } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Filters } from '@/features/restrictions/components/filters'
import { RankingCards } from '@/features/restrictions/components/ranking-cards'
import { Metrics } from '@/features/restrictions/components/metrics'
import { OccurrencesWarning } from '@/features/restrictions/components/occurrences-warning'
import { RestrictionsTable } from '@/features/restrictions/components/restrictions-table'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import {
  matchesSearch,
  sourceLabels,
  useRestrictions,
  type Source,
} from '@/features/restrictions/api/get-restrictions'
import { useSnapshot } from '@/features/snapshot/api/get-snapshot'
import { formatPeriod } from '@/utils/format'

export default function Restrictions() {
  const [search, setSearch] = useState('')
  const [source, setSource] = useState<Source>('eolica')

  const restrictionsQuery = useRestrictions({ source })
  const snapshotQuery = useSnapshot()

  const filteredList = useMemo(() => {
    const items = restrictionsQuery.data?.itens ?? []
    if (search.trim() === '') return items
    return items.filter((item) => matchesSearch(item, search))
  }, [restrictionsQuery.data, search])

  const period = snapshotQuery.data
    ? formatPeriod(snapshotQuery.data.periodo_inicio, snapshotQuery.data.periodo_fim)
    : '—'

  const top = restrictionsQuery.data?.itens[0]

  return (
    <div className="sim-page">
      <main className="mx-auto max-w-screen-2xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        <section className="border-b border-(--sim-border) pb-7">
          <div>
            <p className="sim-eyebrow text-(--sim-brand)">Monitoramento de transmissão</p>
            <h1 className="sim-display mt-2 text-2xl font-semibold text-(--sim-brand-ink) sm:text-3xl">
              Onde o corte custou mais
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-(--sim-muted-foreground)">
              Restrições de linha de transmissão, corte de origem local, razão CNF. Ordenado por
              energia cortada nos últimos 12 meses.
            </p>
          </div>
        </section>

        <div className="py-6">
          {restrictionsQuery.data && <Metrics summary={restrictionsQuery.data.resumo} top={top} />}
        </div>

        <div className="mb-5">
          <Filters
            search={search}
            onSearchChange={setSearch}
            source={source}
            onSourceChange={setSource}
            period={period}
          />
        </div>

        {restrictionsQuery.isPending ? (
          <div className="flex items-center justify-center py-16">
            <Spinner />
          </div>
        ) : restrictionsQuery.isError ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-warning/40 bg-warning-light py-16 text-center">
            <p className="text-sm text-warning">
              Não foi possível carregar as restrições: {restrictionsQuery.error.message}
            </p>
            <Button variant="outline" onClick={() => restrictionsQuery.refetch()}>
              Tentar de novo
            </Button>
          </div>
        ) : filteredList.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-(--sim-border) py-16 text-center">
            <SearchX className="h-6 w-6 text-(--sim-muted-foreground)" aria-hidden="true" />
            <p className="text-sm text-(--sim-muted-foreground)">
              {search.trim() === ''
                ? 'Nenhuma restrição com vínculo aprovado nesta fonte.'
                : `Nenhuma restrição encontrada para "${search}".`}
            </p>
          </div>
        ) : (
          <>
            <section
              className="overflow-hidden rounded-lg border border-(--sim-border) bg-(--sim-surface)"
              aria-label="Ranking de restrições"
            >
              <div className="flex items-center justify-between border-b border-(--sim-border) bg-(--sim-muted)/50 px-4 py-3">
                <div>
                  <h2 className="sim-display text-sm font-semibold text-(--sim-brand-ink)">
                    Ranking de impacto
                  </h2>
                  <p className="mt-0.5 text-xs text-(--sim-muted-foreground)">
                    {filteredList.length} {filteredList.length === 1 ? 'resultado' : 'resultados'} ·
                    fonte {sourceLabels[source]}
                  </p>
                </div>
                <span className="hidden text-xs font-semibold text-(--sim-muted-foreground) sm:block">
                  Energia cortada ↓
                </span>
              </div>

              <div className="lg:hidden">
                <RankingCards items={filteredList} />
              </div>
              <div className="hidden lg:block">
                <RestrictionsTable
                  items={filteredList}
                  occurrencesWarning={restrictionsQuery.data.resumo.aviso_ocorrencias}
                />
              </div>
            </section>

            {/* O limite da coluna Ocorrências, como a API o manda, junto dela. */}
            <OccurrencesWarning className="mt-4 rounded-lg border-(--sim-alert) bg-(--sim-alert-soft)">
              {restrictionsQuery.data.resumo.aviso_ocorrencias}
            </OccurrencesWarning>
          </>
        )}
      </main>
    </div>
  )
}
