import { Copy } from 'lucide-react'
import type { KeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { displayName, type RestrictionListItem } from '../api/get-restrictions'
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from '@/components/ui/context-menu'
import { HeaderTooltip } from '@/components/ui/tooltip'
import { formatInteger, formatMWhAsGWh, formatPercentage } from '@/utils/format'

type RestrictionsTableProps = {
  items: RestrictionListItem[]
  /** O limite da contagem de ocorrências, como a API o manda (`resumo.aviso_ocorrencias`). */
  occurrencesWarning: string
}

export function RestrictionsTable({ items, occurrencesWarning }: RestrictionsTableProps) {
  const navigate = useNavigate()

  function goToDetail(id: string) {
    navigate(`/restricoes/${id}`)
  }

  return (
    <div className="overflow-x-auto">
      <table className="sim-list-table w-full min-w-280 text-xs tabular-nums">
        <thead>
          <tr>
            <th className="w-12">
              <HeaderTooltip label="#">
                Posição no ranking por energia cortada, da maior para a menor.
              </HeaderTooltip>
            </th>
            <th>
              <HeaderTooltip label="Restrição">
                Nome curto montado a partir do texto do ONS: tipo, tensão, subestações e circuito da
                linha monitorada. Quando o texto não cita linha reconhecível, aparece o texto
                original truncado. Passe o mouse para ver o texto inteiro.
              </HeaderTooltip>
            </th>
            <th>Fatia do total</th>
            <th data-align="right">
              <HeaderTooltip label="Energia cortada (GWh)">
                Energia que deixou de ser gerada por causa desta restrição nos 12 meses, na fonte
                filtrada. 1 GWh = 1.000 MWh.
              </HeaderTooltip>
            </th>
            <th data-align="right">Do total</th>
            <th data-align="right">
              <HeaderTooltip label="Ocorrências">{occurrencesWarning}</HeaderTooltip>
            </th>
            <th data-align="right">Linhas</th>
            <th>Subestações</th>
            <th>
              <HeaderTooltip label="Instrução de Operação">
                Código do documento do ONS que fixa o limite desta restrição, como IO-ON.NE.5NE. É
                por ele que o operador acha a regra. Vazio quando o texto não traz o código.
              </HeaderTooltip>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={9} className="py-8 text-center text-(--sim-muted-foreground)">
                Nenhuma restrição adicional para este filtro.
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <ContextMenu key={item.id}>
                <ContextMenuTrigger asChild>
                  <tr
                    tabIndex={0}
                    role="link"
                    aria-label={`Ver detalhes de ${displayName(item, 60)}`}
                    className="cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-(--sim-ring)"
                    onClick={() => goToDetail(item.id)}
                    onKeyDown={(event: KeyboardEvent<HTMLTableRowElement>) => {
                      if (event.key === 'Enter') goToDetail(item.id)
                    }}
                  >
                    <td>
                      <span className="sim-rank-number">{item.posicao}</span>
                    </td>
                    <td title={item.texto}>
                      <div className="text-[0.8125rem] font-bold text-(--sim-brand-ink)">
                        {displayName(item, 90)}
                      </div>
                    </td>
                    <td>
                      <div
                        className="sim-bar min-w-24"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={Math.round(item.fatia_do_total * 100)}
                        aria-label={`Fatia de ${displayName(item, 40)} no total cortado`}
                      >
                        <div style={{ width: `${Math.max(item.fatia_do_total * 100, 0.5)}%` }} />
                      </div>
                    </td>
                    <td
                      data-align="right"
                      className="font-bold tabular-nums text-(--sim-brand-ink)"
                    >
                      {formatMWhAsGWh(item.energia_mwh)}
                    </td>
                    <td data-align="right" className="tabular-nums">
                      {formatPercentage(item.fatia_do_total * 100)}%
                    </td>
                    <td data-align="right" className="tabular-nums text-(--sim-muted-foreground)">
                      {item.ocorrencias == null ? '—' : formatInteger(item.ocorrencias)}
                    </td>
                    <td data-align="right" className="tabular-nums">
                      {formatInteger(item.equipamentos)}
                    </td>
                    <td className="whitespace-normal leading-4 text-(--sim-muted-foreground)">
                      {item.subestacoes.join(' · ')}
                    </td>
                    <td className="text-(--sim-muted-foreground)">
                      {item.instrucao_operacao ?? '—'}
                    </td>
                  </tr>
                </ContextMenuTrigger>
                <ContextMenuContent>
                  <ContextMenuItem asChild>
                    <Link to={`/restricoes/${item.id}`}>Ver detalhes</Link>
                  </ContextMenuItem>
                  <ContextMenuItem onSelect={() => navigator.clipboard.writeText(item.texto)}>
                    <Copy className="h-4 w-4" aria-hidden="true" />
                    Copiar texto do ONS
                  </ContextMenuItem>
                </ContextMenuContent>
              </ContextMenu>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
