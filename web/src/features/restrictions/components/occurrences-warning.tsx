import { TriangleAlert } from 'lucide-react'
import { cn } from '@/utils/cn'

type OccurrencesWarningProps = {
  /** O limite da contagem, como a API o manda (`aviso` e `aviso_ocorrencias`). */
  children: string
  className?: string
}

/** O aviso que acompanha qualquer contagem de ocorrências: número de auditoria, e não de vitrine. */
export function OccurrencesWarning({ children, className }: OccurrencesWarningProps) {
  return (
    <div
      role="note"
      className={cn(
        'flex items-start gap-3 rounded-lg border border-warning bg-surface px-4 py-3',
        className,
      )}
    >
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
      <p className="text-sm text-text-secondary">{children}</p>
    </div>
  )
}
