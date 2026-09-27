import { Search, SearchX } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useSimulations } from '@/features/saved-simulations/api/get-simulations'
import { modalityLabels } from '@/features/saved-simulations/api/labels'
import { RestrictionPickerDialog } from '@/features/simulations/components/restriction-picker-dialog'
import { SimulationItem } from '@/features/saved-simulations/components/list/simulation-item'
import { SnapshotBanner } from '@/features/saved-simulations/components/list/snapshot-banner'
import { useSnapshot } from '@/features/snapshot/api/get-snapshot'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { truncateText, withoutControlPrefix } from '@/utils/format'

const ALL = 'todas'

/** Simulações salvas: uma linha por simulação, com o histórico de revisões dentro. */
export default function Simulations() {
  const navigate = useNavigate()
  const simulationsQuery = useSimulations()
  const snapshotQuery = useSnapshot()

  // O filtro de restrição mora na URL (`?restricao=<id>&nome=<texto>`): "Ver simulações" chega
  // por ela, e mudar o seletor a reescreve. Assim a URL nunca aponta para outra restrição que não
  // a da tela, e recarregar ou voltar mantém o filtro.
  const [searchParams, setSearchParams] = useSearchParams()
  const urlRestrictionId = searchParams.get('restricao')
  const urlRestrictionName = searchParams.get('nome')
  const restrictionId = urlRestrictionId ?? ALL

  const [search, setSearch] = useState('')
  const [modality, setModality] = useState(ALL)
  const [selected, setSelected] = useState<number[]>([])
  const [expanded, setExpanded] = useState<number[] | null>(null)

  const simulations = simulationsQuery.data
  const activeSnapshotId = snapshotQuery.data?.id

  const restrictions = useMemo(() => {
    const byId = new Map<string, string>()
    for (const simulation of simulations ?? []) {
      byId.set(simulation.restricao_id, simulation.restricao_texto ?? simulation.restricao_id)
    }
    // A restrição pedida pela URL pode não ter nenhuma simulação salva ainda: sem isto, o
    // seletor mostraria o filtro em branco em vez do nome da restrição escolhida.
    if (urlRestrictionId && !byId.has(urlRestrictionId)) {
      byId.set(urlRestrictionId, urlRestrictionName ?? urlRestrictionId)
    }
    return [...byId]
  }, [simulations, urlRestrictionId, urlRestrictionName])

  function changeRestriction(id: string) {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (id === ALL) {
          next.delete('restricao')
          next.delete('nome')
        } else {
          next.set('restricao', id)
          next.set('nome', restrictions.find(([key]) => key === id)?.[1] ?? id)
        }
        return next
      },
      { replace: true },
    )
  }

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return (simulations ?? []).filter((simulation) => {
      if (restrictionId !== ALL && simulation.restricao_id !== restrictionId) return false
      if (modality !== ALL && simulation.modalidade !== modality) return false
      if (!term) return true
      return `${simulation.nome} ${simulation.restricao_texto ?? ''}`.toLowerCase().includes(term)
    })
  }, [simulations, search, restrictionId, modality])

  const isOutdated = (revisions: { atual: boolean; snapshot_id: string }[]) => {
    const current = revisions.find((revision) => revision.atual)
    return Boolean(activeSnapshotId && current && current.snapshot_id !== activeSnapshotId)
  }
  const outdatedCount = (simulations ?? []).filter((item) => isOutdated(item.revisoes)).length
  const revisionsCount = filtered.reduce((sum, item) => sum + item.revisoes.length, 0)

  // Por padrão todas as simulações abrem o histórico.
  const openIds = expanded ?? filtered.map((item) => item.id)
  const toggle = (id: number) =>
    setExpanded(openIds.includes(id) ? openIds.filter((item) => item !== id) : [...openIds, id])

  // Comparar exige duas simulações da mesma restrição: somar recuperação de gargalos diferentes
  // é somar o que não se soma. Cada uma entra na revisão atual.
  const chosen = (simulations ?? []).filter((item) => selected.includes(item.id))
  const sameRestriction = chosen.length === 2 && chosen[0].restricao_id === chosen[1].restricao_id
  const canCompare = sameRestriction
  const compareHint =
    chosen.length === 2 && !sameRestriction
      ? 'Só é possível comparar simulações da mesma restrição.'
      : chosen.length === 2
        ? undefined
        : 'Marque duas simulações para comparar.'

  function compareSelected() {
    const [a, b] = chosen.map((item) => item.revisoes.find((revision) => revision.atual)?.id)
    if (a && b) navigate(`/comparar?a=${a}&b=${b}`)
  }

  function toggleSelected(id: number, checked: boolean) {
    setSelected((current) => (checked ? [...current, id] : current.filter((item) => item !== id)))
  }

  const countLabel = simulations
    ? `${filtered.length} ${filtered.length === 1 ? 'simulação' : 'simulações'} · ${revisionsCount} ${revisionsCount === 1 ? 'revisão' : 'revisões'}`
    : null

  return (
    <div className="sim-page">
      <main className="mx-auto flex max-w-screen-2xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        <section className="flex flex-col gap-5 border-b border-(--sim-border) pb-7 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="sim-display text-2xl font-semibold text-(--sim-brand-ink) sm:text-3xl">
              Simulações
            </h1>
            {countLabel && (
              <p className="mt-2 text-sm text-(--sim-muted-foreground)">{countLabel}</p>
            )}
          </div>
          <div className="flex flex-col items-start gap-1.5 lg:items-end">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="sim-btn-secondary gap-1 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!canCompare}
                onClick={compareSelected}
                title={compareHint}
              >
                Comparar selecionadas <span className="font-normal">({selected.length})</span>
              </button>
              <RestrictionPickerDialog
                title="Nova simulação"
                description="Escolha a restrição que a simulação vai analisar. Ordenadas por energia cortada nos últimos 12 meses."
                trigger={
                  <button type="button" className="sim-btn-primary">
                    Nova simulação
                  </button>
                }
              />
            </div>
            {compareHint && selected.length > 0 && (
              <span className="text-xs text-(--sim-muted-foreground)">{compareHint}</span>
            )}
          </div>
        </section>

        {snapshotQuery.data && outdatedCount > 0 && (
          <SnapshotBanner
            snapshotId={snapshotQuery.data.id}
            loadedAt={snapshotQuery.data.carregado_em}
            outdatedCount={outdatedCount}
          />
        )}

        <section
          aria-label="Busca e filtros"
          className="grid gap-4 rounded-lg border border-(--sim-border) bg-(--sim-surface) p-3 sm:p-4 lg:grid-cols-[minmax(260px,1fr)_minmax(220px,1fr)_minmax(200px,auto)]"
        >
          <div>
            <label htmlFor="busca" className="sim-filter-label">
              Buscar
            </label>
            <span className="relative mt-2 block">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-(--sim-muted-foreground)"
                aria-hidden="true"
              />
              <input
                id="busca"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Nome ou restrição"
                className="sim-filter-input pr-3 pl-9"
              />
            </span>
          </div>
          <div>
            <label htmlFor="restricao" className="sim-filter-label">
              Restrição
            </label>
            <Select
              id="restricao"
              value={restrictionId}
              onChange={(event) => changeRestriction(event.target.value)}
              containerClassName="mt-2"
              className="sim-filter-input"
            >
              <option value={ALL}>Todas</option>
              {restrictions.map(([id, text]) => (
                <option key={id} value={id}>
                  {truncateText(withoutControlPrefix(text), 60)}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label htmlFor="modalidade" className="sim-filter-label">
              Modalidade
            </label>
            <Select
              id="modalidade"
              value={modality}
              onChange={(event) => setModality(event.target.value)}
              containerClassName="mt-2"
              className="sim-filter-input"
            >
              <option value={ALL}>Todas</option>
              {Object.entries(modalityLabels).map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </Select>
          </div>
        </section>

        {simulationsQuery.isPending ? (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        ) : simulationsQuery.isError ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-warning/40 bg-warning-light py-16 text-center">
            <p className="text-sm text-warning">
              Não foi possível carregar as simulações: {simulationsQuery.error.message}
            </p>
            <Button type="button" variant="outline" onClick={() => simulationsQuery.refetch()}>
              Tentar de novo
            </Button>
          </div>
        ) : (simulations?.length ?? 0) === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-(--sim-border) py-16 text-center">
            <p className="text-sm text-(--sim-muted-foreground)">
              Nenhuma simulação salva ainda. Uma simulação nasce de uma restrição.
            </p>
            <Link to="/" className="sim-btn-secondary">
              Ver restrições
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-(--sim-border) py-16 text-center">
            <SearchX className="h-6 w-6 text-(--sim-muted-foreground)" aria-hidden="true" />
            <p className="text-sm text-(--sim-muted-foreground)">
              Nenhuma simulação encontrada para este filtro.
            </p>
          </div>
        ) : (
          <div className="flex min-w-0 flex-col gap-4">
            {filtered.map((simulation) => (
              <SimulationItem
                key={simulation.id}
                simulation={simulation}
                selected={selected.includes(simulation.id)}
                onSelectedChange={(checked) => toggleSelected(simulation.id, checked)}
                expanded={openIds.includes(simulation.id)}
                onToggle={() => toggle(simulation.id)}
                outdated={isOutdated(simulation.revisoes)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
