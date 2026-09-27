import { useState } from 'react'
import { OccurrencesWarning } from './occurrences-warning'
import { useRestrictionOccurrences } from '../api/get-restriction-occurrences'
import type { Source } from '../api/get-restrictions'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { HeaderTooltip, InfoTooltip } from '@/components/ui/tooltip'
import {
  formatDateTime,
  formatInteger,
  formatMWhAsGWh,
  formatNumber,
  formatSnapshotId,
} from '@/utils/format'

/** Quantas ocorrências a tabela mostra por vez; a API manda todas, da maior energia para a menor. */
const PAGE_SIZE = 20

type RestrictionOccurrencesTableProps = {
  restrictionId: string
  source: Source
}

export function RestrictionOccurrencesTable({
  restrictionId,
  source,
}: RestrictionOccurrencesTableProps) {
  const query = useRestrictionOccurrences({ restrictionId, source })
  const [visible, setVisible] = useState(PAGE_SIZE)

  return (
    <section className="sim-card mt-5" aria-labelledby="ocorrencias">
      {query.isPending ? (
        <>
          <div className="border-b border-(--sim-border) px-5 py-4">
            <OccurrencesHeading />
          </div>
          <div className="flex items-center justify-center py-10">
            <Spinner />
          </div>
        </>
      ) : query.isError ? (
        <>
          <div className="border-b border-(--sim-border) px-5 py-4">
            <OccurrencesHeading />
          </div>
          <div className="m-5 flex flex-col items-center gap-2 rounded-lg border border-dashed border-warning/40 bg-warning-light py-10 text-center">
            <p className="text-sm text-warning">
              Não foi possível carregar as ocorrências: {query.error.message}
            </p>
            <Button variant="outline" onClick={() => query.refetch()}>
              Tentar de novo
            </Button>
          </div>
        </>
      ) : (
        <Occurrences
          data={query.data}
          visible={visible}
          onShowMore={() => setVisible((current) => current + PAGE_SIZE)}
        />
      )}
    </section>
  )
}

function OccurrencesHeading() {
  return (
    <h2
      id="ocorrencias"
      className="sim-display flex items-center gap-1.5 text-base font-semibold text-(--sim-brand-ink)"
    >
      Ocorrências
      <InfoTooltip label="Ajuda: Ocorrências">
        Episódio de corte: meias horas seguidas com corte, sem folga. Contagem sensível a artefato
        de apuração; serve para auditoria, não como vitrine.
      </InfoTooltip>
    </h2>
  )
}

type OccurrencesProps = {
  data: NonNullable<ReturnType<typeof useRestrictionOccurrences>['data']>
  visible: number
  onShowMore: () => void
}

function Occurrences({ data, visible, onShowMore }: OccurrencesProps) {
  const shown = data.itens.slice(0, visible)

  return (
    <>
      <div className="border-b border-(--sim-border) px-5 py-4">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <OccurrencesHeading />
            <p className="mt-1 text-xs text-(--sim-muted-foreground)">
              {formatInteger(data.total)} {data.total === 1 ? 'ocorrência' : 'ocorrências'} no
              período, {formatMWhAsGWh(data.energia_mwh)} GWh cortados.
            </p>
          </div>
          <span className="text-xs font-semibold text-(--sim-muted-foreground)">
            Ordenadas por energia ↓
          </span>
        </div>

        {/* O limite do número vem da API e fica junto dele: número de auditoria, e não de vitrine. */}
        <OccurrencesWarning className="mt-4 rounded-lg border-(--sim-alert) bg-(--sim-alert-soft) px-3 py-2.5 [&_p]:text-xs [&_p]:leading-5 [&_p]:text-(--sim-muted-foreground)">
          {data.aviso}
        </OccurrencesWarning>
      </div>

      {data.itens.length === 0 ? (
        <div className="m-5 rounded-lg border border-dashed border-(--sim-border) py-10 text-center text-sm text-(--sim-muted-foreground)">
          Sem ocorrência de corte nesta fonte, no período do snapshot{' '}
          {formatSnapshotId(data.snapshot_id)}.
        </div>
      ) : (
        <>
          <div className="divide-y divide-(--sim-border) lg:hidden">
            {shown.map((occurrence) => (
              <article key={occurrence.inicio} className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-extrabold uppercase text-(--sim-muted-foreground)">
                      Início
                    </p>
                    <p className="mt-1 text-sm font-bold text-(--sim-brand-ink)">
                      {formatDateTime(occurrence.inicio)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-extrabold uppercase text-(--sim-muted-foreground)">
                      Energia
                    </p>
                    <p className="sim-display mt-1 text-sm font-semibold text-(--sim-brand)">
                      {formatNumber(occurrence.energia_mwh, 1)} MWh
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-(--sim-muted-foreground)">Fim</span>
                    <strong className="mt-1 block text-(--sim-brand-ink)">
                      {formatDateTime(occurrence.fim)}
                    </strong>
                  </div>
                  <div>
                    <span className="text-(--sim-muted-foreground)">Duração</span>
                    <strong className="mt-1 block text-(--sim-brand-ink)">
                      {formatNumber(occurrence.duracao_horas, 1)} h
                    </strong>
                  </div>
                  <div>
                    <span className="text-(--sim-muted-foreground)">Pico médio</span>
                    <strong className="mt-1 block text-(--sim-brand-ink)">
                      {formatNumber(occurrence.corte_medio_maximo_mw, 1)} MW
                    </strong>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="hidden overflow-x-auto lg:block">
            <table className="sim-list-table w-full min-w-245 text-xs tabular-nums">
              <thead>
                <tr>
                  <th>Início</th>
                  <th>Fim</th>
                  <th data-align="right">Duração (h)</th>
                  <th data-align="right">Meias horas com corte</th>
                  <th data-align="right">Energia cortada (MWh)</th>
                  <th data-align="right">
                    <HeaderTooltip label="Corte médio máximo (MW)">
                      Maior potência média de meia hora do episódio. Não é o pico: a série do ONS é
                      média da meia hora. Cem MW médios com 10 minutos de corte são 300 MW de pico.
                    </HeaderTooltip>
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((occurrence) => (
                  <tr key={occurrence.inicio}>
                    <td className="text-(--sim-muted-foreground)">
                      {formatDateTime(occurrence.inicio)}
                    </td>
                    <td className="text-(--sim-muted-foreground)">
                      {formatDateTime(occurrence.fim)}
                    </td>
                    <td data-align="right" className="text-(--sim-muted-foreground)">
                      {formatNumber(occurrence.duracao_horas, 1)}
                    </td>
                    <td data-align="right" className="text-(--sim-muted-foreground)">
                      {formatInteger(occurrence.intervalos)}
                    </td>
                    <td data-align="right" className="font-semibold text-(--sim-brand-ink)">
                      {formatNumber(occurrence.energia_mwh, 1)}
                    </td>
                    <td data-align="right" className="font-semibold text-(--sim-brand-ink)">
                      {formatNumber(occurrence.corte_medio_maximo_mw, 1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="sim-card-head flex flex-col gap-3 border-t border-(--sim-border) px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-(--sim-muted-foreground)">
              Mostrando {formatInteger(shown.length)} de {formatInteger(data.itens.length)}{' '}
              ocorrências, da maior energia para a menor.
            </p>
            {shown.length < data.itens.length && (
              <Button variant="outline" size="sm" onClick={onShowMore}>
                Mostrar mais
              </Button>
            )}
          </div>
        </>
      )}
    </>
  )
}
