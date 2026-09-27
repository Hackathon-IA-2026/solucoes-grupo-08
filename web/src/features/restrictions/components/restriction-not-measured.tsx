import { TriangleAlert } from 'lucide-react'
import type { DetailedRestriction } from '../api/get-restriction'
import { cn } from '@/utils/cn'
import { formatSnapshotId } from '@/utils/format'

type RestrictionNotMeasuredProps = {
  item: DetailedRestriction
  className?: string
}

/**
 * A restrição existe como identidade, mas não foi medida no snapshot ativo: energia e fatia vêm
 * zeradas e o texto é o primeiro visto. O aviso evita ler esses zeros como "não cortou".
 */
export function RestrictionNotMeasured({ item, className }: RestrictionNotMeasuredProps) {
  if (item.presente_no_snapshot) return null

  return (
    <div
      role="status"
      className={cn(
        'flex items-start gap-3 rounded-lg border border-warning bg-surface px-4 py-3',
        className,
      )}
    >
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
      <p className="text-sm text-text-secondary">
        Esta restrição não foi medida no snapshot {formatSnapshotId(item.snapshot_id)}. Os valores
        de energia aparecem zerados e o texto é o primeiro que o ONS publicou para ela. Ela deixou
        de cortar ou o ONS reescreveu o texto e ela virou outra.
      </p>
    </div>
  )
}
