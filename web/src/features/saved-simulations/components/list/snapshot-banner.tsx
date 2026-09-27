import { AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatDate, formatSnapshotId } from '@/utils/format'

type SnapshotBannerProps = {
  snapshotId: string
  loadedAt: string
  outdatedCount: number
}

/** Avisa quando há simulação calculada sobre um snapshot que não é mais o ativo. */
export function SnapshotBanner({ snapshotId, loadedAt, outdatedCount }: SnapshotBannerProps) {
  return (
    <div
      role="status"
      className="flex flex-col gap-3 rounded-lg border border-(--sim-alert) bg-(--sim-alert-soft) px-4 py-3 sm:flex-row sm:items-center sm:gap-4"
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className="inline-flex shrink-0">
            <Badge variant="warning" className="gap-1.5">
              <AlertCircle className="h-3 w-3" aria-hidden="true" />
              Dado novo do ONS
            </Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>
          Snapshot: cópia datada do dado do ONS. Quando entra uma nova, as simulações antigas
          continuam válidas, mas foram calculadas com a anterior.
        </TooltipContent>
      </Tooltip>
      <span className="text-xs leading-5 text-(--sim-muted-foreground)">
        O ONS publicou a versão <span>{formatSnapshotId(snapshotId)}</span>, carregada em{' '}
        <span>{formatDate(loadedAt)}</span>. {outdatedCount}{' '}
        {outdatedCount === 1
          ? 'simulação foi calculada com a versão anterior'
          : 'simulações foram calculadas com a versão anterior'}
        ; o recálculo fica no item dela.
      </span>
    </div>
  )
}
