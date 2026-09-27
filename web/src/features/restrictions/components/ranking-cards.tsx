import { Link } from 'react-router'
import { displayName, type RestrictionListItem } from '../api/get-restrictions'
import { formatInteger, formatMWhAsGWh, formatPercentage } from '@/utils/format'

/** O ranking como lista de cartões, para o celular. Os mesmos dados da tabela. */
export function RankingCards({ items }: { items: RestrictionListItem[] }) {
  return (
    <div className="divide-y divide-(--sim-border)">
      {items.map((item) => (
        <Link
          key={item.id}
          to={`/restricoes/${item.id}`}
          aria-label={`Ver detalhes de ${displayName(item, 60)}`}
          className="block p-4 hover:bg-(--sim-muted)"
        >
          <div className="flex min-w-0 items-start gap-3">
            <span className="sim-rank-number">{item.posicao}</span>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold leading-5 text-(--sim-brand-ink)">
                {displayName(item, 90)}
              </h3>
              <p className="mt-1 truncate text-xs text-(--sim-muted-foreground)">
                {item.subestacoes.join(' · ')}
              </p>
              <div className="sim-bar mt-3" aria-hidden="true">
                <div style={{ width: `${Math.max(item.fatia_do_total * 100, 0.5)}%` }} />
              </div>
            </div>
          </div>
          <div className="mt-3 flex items-end justify-between pl-9">
            <span className="text-xs font-semibold text-(--sim-brand)">
              {formatPercentage(item.fatia_do_total * 100)}% do total
            </span>
            <div className="text-right">
              <strong className="sim-display block text-base text-(--sim-brand-ink)">
                {formatMWhAsGWh(item.energia_mwh)} GWh
              </strong>
              {item.ocorrencias != null && (
                <span className="text-xs text-(--sim-muted-foreground)">
                  {formatInteger(item.ocorrencias)} ocorrências
                </span>
              )}
            </div>
          </div>
        </Link>
      ))}
    </div>
  )
}
