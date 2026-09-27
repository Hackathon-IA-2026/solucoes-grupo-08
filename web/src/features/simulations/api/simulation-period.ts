import type { Snapshot } from '@/features/snapshot/api/get-snapshot'

export type SimulationPeriodMonth = {
  label: string
  year: number
}

export type SimulationWindow = {
  /** Primeira meia hora da janela, já formatada: `01/09/2025` e `00:00`. */
  start: { date: string; time: string }
  /** Última meia hora da janela. `periodo_fim` do snapshot é exclusivo, então é meia hora antes. */
  end: { date: string; time: string }
  months: SimulationPeriodMonth[]
}

const HALF_HOUR_MS = 30 * 60 * 1000

const formatDate = (date: Date) =>
  date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })

const formatTime = (date: Date) =>
  date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })

/**
 * A janela analisada, como a tela a mostra. Vem do snapshot (`periodo_inicio` e `periodo_fim`), e
 * não da data de hoje: é o dado do ONS que define o período, o pedido de simulação não o aceita, e
 * a interface só o exibe. Sem janela declarada no snapshot, não há o que mostrar.
 */
export function simulationWindow(snapshot: Snapshot | undefined): SimulationWindow | undefined {
  if (!snapshot?.periodo_inicio || !snapshot.periodo_fim) return undefined

  const start = new Date(snapshot.periodo_inicio)
  const endExclusive = new Date(snapshot.periodo_fim)
  const lastHalfHour = new Date(endExclusive.getTime() - HALF_HOUR_MS)

  const months: SimulationPeriodMonth[] = []
  for (
    const month = new Date(start.getFullYear(), start.getMonth(), 1);
    month < endExclusive;
    month.setMonth(month.getMonth() + 1)
  ) {
    months.push({
      label: month.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''),
      year: month.getFullYear(),
    })
  }

  return {
    start: { date: formatDate(start), time: formatTime(start) },
    end: { date: formatDate(lastHalfHour), time: formatTime(lastHalfHour) },
    months,
  }
}
