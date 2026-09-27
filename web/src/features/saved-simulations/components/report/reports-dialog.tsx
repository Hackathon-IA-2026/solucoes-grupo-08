import { LoaderCircle } from 'lucide-react'
import { useReports } from '../../api/report'
import { useGenerateReport } from '../../api/use-generate-report'
import { ReportsList } from './reports-list'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

type ReportsDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  simulationId: number
}

/**
 * Os relatórios da simulação num modal: lista, gera um novo e abre exatamente o escolhido. A lista
 * só é buscada com o modal aberto.
 */
export function ReportsDialog({ open, onOpenChange, simulationId }: ReportsDialogProps) {
  const reports = useReports({ simulationId, enabled: open })
  const { generate, generating, error } = useGenerateReport(simulationId, reports)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        {/* pr-8: o X de fechar do modal fica no canto, e o botão não pode ficar sob ele. */}
        <div className="flex items-center justify-between gap-4 pr-8">
          <div className="min-w-0">
            <DialogTitle className="sim-display text-(--sim-brand-ink)">Relatórios</DialogTitle>
            <DialogDescription className="mt-1 text-(--sim-muted-foreground)">
              Cada relatório resume as revisões da simulação até o momento em que foi gerado.
            </DialogDescription>
          </div>
          <button
            type="button"
            onClick={generate}
            disabled={generating}
            className="sim-btn-primary shrink-0 gap-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {generating && (
              <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />
            )}
            {generating ? 'Gerando relatório…' : 'Gerar relatório'}
          </button>
        </div>
        {error && (
          <div role="alert" className="mt-3 flex items-center gap-3 text-xs text-danger">
            <span>Erro ao gerar relatório: {error.message}</span>
            <button type="button" className="sim-btn-secondary" onClick={generate}>
              Tentar novamente
            </button>
          </div>
        )}
        <div className="mt-4">
          <ReportsList simulationId={simulationId} reports={reports} />
        </div>
      </DialogContent>
    </Dialog>
  )
}
