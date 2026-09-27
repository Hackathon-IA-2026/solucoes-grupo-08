import { useRef } from 'react'
import { useNavigate } from 'react-router'
import { useCreateReport, useReports } from './report'

/**
 * Gerar relatório da simulação: o relatório novo abre na hora, porque a tela dele mostra o
 * carregamento até a geração terminar. `generating` vale também quando outro já está sendo gerado.
 */
export function useGenerateReport(simulationId: number, reports: ReturnType<typeof useReports>) {
  const navigate = useNavigate()
  const createReport = useCreateReport({ simulationId })
  // `isPending` só muda no render seguinte: um segundo clique no mesmo instante passaria por ele.
  const requesting = useRef(false)
  const generating = createReport.isPending || reports.data?.some((r) => r.estado === 'gerando')

  function generate() {
    if (requesting.current) return
    requesting.current = true
    createReport.mutate(undefined, {
      onSuccess: (created) => navigate(`/simulacoes/${simulationId}/relatorios/${created.id}`),
      onSettled: () => {
        requesting.current = false
      },
    })
  }

  return { generate, generating, error: createReport.isError ? createReport.error : null }
}
