import { MoreHorizontal } from 'lucide-react'
import { Link } from 'react-router'
import type { SimulationListItem } from '../../api/get-simulations'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { HeaderTooltip, Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'
import { formatDate, formatNumber, formatSnapshotId } from '@/utils/format'

/**
 * As revisões de uma simulação, da mais nova para a mais velha. "O que mudou" e os números vêm
 * prontos da listagem. "Criar revisão" reabre a Nova simulação como cópia daquela revisão salva.
 * O menu de ações tem coluna própria, separada do VPL.
 *
 * Larguras fixas por `<colgroup>`, para o cabeçalho e as linhas alinharem. "O que mudou" trunca
 * numa linha e mostra o texto inteiro num tooltip ao passar o mouse ou focar, para a linha da
 * tabela não crescer com texto longo. A rolagem lateral, quando a tabela não cabe, vem de `Table`.
 */
export function RevisionsTable({ simulation }: { simulation: SimulationListItem }) {
  const { revisoes: revisions, restricao_id: restrictionId } = simulation

  return (
    <>
      <div className="relative overflow-x-auto">
        <table className="sim-list-table w-full min-w-250 table-fixed text-xs">
          <colgroup>
            <col className="w-10" />
            <col className="w-32" />
            <col className="w-70" />
            <col className="w-30" />
            <col className="w-50" />
            <col className="w-35" />
            <col className="w-50" />
            <col className="w-12" />
          </colgroup>
          <thead>
            <tr>
              <th>
                <span className="sr-only">Atual</span>
              </th>
              <th>
                <HeaderTooltip label="Revisão">
                  Cada cálculo salvo. &quot;rev 1&quot; é o primeiro; alterar e recalcular cria a
                  próxima. Nada se apaga.
                </HeaderTooltip>
              </th>
              <th>O que mudou</th>
              <th>Data</th>
              <th>
                <HeaderTooltip label="Dado ONS · método">
                  Versão do snapshot e versão das regras de cálculo usadas. Duas revisões com
                  versões diferentes não são comparáveis lado a lado sem ressalva.
                </HeaderTooltip>
              </th>
              <th>Energia recuperada</th>
              <th>
                <HeaderTooltip label="VPL">
                  Valor Presente Líquido: benefício menos custo, tudo trazido a hoje pela taxa de
                  desconto. Positivo indica que se paga à taxa escolhida.
                </HeaderTooltip>
              </th>
              <th>
                <span className="sr-only">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {revisions.map((revision) => (
              <tr key={revision.id} className={cn(revision.atual && 'bg-(--sim-sky-soft)/25')}>
                <td>
                  <span
                    className={cn(
                      'block size-2.5 rounded-full border-2',
                      revision.atual
                        ? 'border-(--sim-brand) bg-(--sim-brand)'
                        : 'border-(--sim-border)',
                    )}
                    aria-hidden="true"
                  />
                </td>
                <td className="whitespace-nowrap font-bold text-(--sim-brand-ink)">
                  rev {revision.posicao}
                  {revision.atual && (
                    <span className="sim-tag ml-1.5" aria-label="revisão atual">
                      Atual
                    </span>
                  )}
                </td>
                <td>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="block truncate text-(--sim-foreground)">
                        {revision.o_que_mudou}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>{revision.o_que_mudou}</TooltipContent>
                  </Tooltip>
                </td>
                <td className="text-(--sim-muted-foreground)">{formatDate(revision.criada_em)}</td>
                <td className="text-(--sim-muted-foreground)">
                  versão {formatSnapshotId(revision.snapshot_id)} · método v{revision.metodo_versao}
                </td>
                <td className="font-semibold tabular-nums text-(--sim-brand-ink)">
                  {revision.energia_recuperada_mwh == null
                    ? '—'
                    : `${formatNumber(revision.energia_recuperada_mwh)} MWh`}
                </td>
                <td className="font-semibold tabular-nums text-(--sim-brand-ink)">
                  {revision.vpl_reais == null ? '—' : `R$ ${formatNumber(revision.vpl_reais)}`}
                </td>
                <td>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        aria-label={`Ações da revisão ${revision.posicao}`}
                      >
                        <MoreHorizontal aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem asChild>
                        <Link to={`/simulacoes/${revision.id}`}>Abrir</Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link
                          to={`/restricoes/${restrictionId}/nova-simulacao?revisar=${revision.id}`}
                        >
                          Duplicar revisão
                        </Link>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {revisions.length > 1 && (
        <p className="sim-card-head border-t border-(--sim-border) px-5 py-3 text-xs text-(--sim-muted-foreground)">
          Comparar revisões:{' '}
          {revisions.slice(0, -1).map((revision, index) => (
            <span key={revision.id}>
              {index > 0 && ' · '}
              <Link
                to={`/comparar?a=${revision.id}&b=${revisions[index + 1].id}`}
                className="font-semibold text-(--sim-brand) hover:underline"
              >
                rev {revision.posicao} contra rev {revisions[index + 1].posicao}
              </Link>
            </span>
          ))}
        </p>
      )}
    </>
  )
}
