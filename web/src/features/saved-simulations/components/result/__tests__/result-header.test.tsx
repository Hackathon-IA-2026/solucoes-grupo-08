import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useReports } from '../../../api/report'
import { ResultHeader } from '../result-header'
import { TooltipProvider } from '@/components/ui/tooltip'

vi.mock('../../../api/report', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useReports: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(useReports).mockReturnValue({ isPending: true } as never)
})

afterEach(cleanup)

const revision = {
  id: 20,
  simulacao_id: 7,
  nome: 'Bateria 100 MW',
  pergunta: null,
  restricao_id: 'R1',
  snapshot_id: '2026-09-21',
  metodo_versao: '0.5.1',
  periodo_inicio: '2025-09-01T00:00:00',
  periodo_fim: '2026-09-01T00:00:00',
  configuracao: { modalidade: 'bateria' },
  revisoes: [{ id: 20, posicao: 1, atual: true, criada_em: '2026-09-20T12:00:00Z' }],
}

function CurrentPath() {
  return <p data-testid="path">{useLocation().pathname}</p>
}

function renderHeader() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/simulacoes/20']}>
        <TooltipProvider>
          <Routes>
            <Route
              path="/simulacoes/:revisaoId"
              element={
                <>
                  <ResultHeader revision={revision as never} />
                  <CurrentPath />
                </>
              }
            />
          </Routes>
        </TooltipProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('result header', () => {
  it('explains the revision and the ONS snapshot version in tooltips', async () => {
    renderHeader()

    fireEvent.focus(screen.getByRole('button', { name: 'Ajuda: Revisão' }))
    expect((await screen.findByRole('tooltip')).textContent).toContain('revisão nova')

    fireEvent.focus(screen.getByRole('button', { name: 'Ajuda: dado ONS versão' }))
    expect((await screen.findByRole('tooltip')).textContent).toContain('Snapshot')
  })

  it('the reports button opens the reports in a dialog, without leaving the page', () => {
    renderHeader()

    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Relatórios' }))

    expect(screen.getByRole('dialog').textContent).toContain('Relatórios')
    expect(screen.getByTestId('path').textContent).toBe('/simulacoes/20')
    // A lista só é buscada com o modal aberto.
    expect(vi.mocked(useReports).mock.calls.at(0)?.[0]).toMatchObject({ enabled: false })
    expect(vi.mocked(useReports).mock.calls.at(-1)?.[0]).toMatchObject({
      simulationId: 7,
      enabled: true,
    })
  })
})
