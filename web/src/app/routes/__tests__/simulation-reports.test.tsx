import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SimulationReports from '../simulation-reports'
import { useCreateReport, useReports } from '@/features/saved-simulations/api/report'

vi.mock('@/features/saved-simulations/api/report', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useReports: vi.fn(),
  useCreateReport: vi.fn(),
}))

afterEach(cleanup)

const item = (id: number, estado: string, extra: object = {}) => ({
  id,
  estado,
  gerado_em: '2026-09-23T12:00:00Z',
  revisoes_cobertas: [1, 2],
  revisoes_novas: [],
  ...extra,
})

const mutate = vi.fn()

function CurrentPath() {
  return <p data-testid="path">{useLocation().pathname}</p>
}

function renderPage(list: object, create: object = {}) {
  vi.mocked(useReports).mockReturnValue(list as never)
  vi.mocked(useCreateReport).mockReturnValue({ mutate, isPending: false, ...create } as never)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/simulacoes/4/relatorios']}>
        <Routes>
          <Route path="/simulacoes/:simulacaoId/relatorios" element={<SimulationReports />} />
          <Route
            path="/simulacoes/:simulacaoId/relatorios/:relatorioId"
            element={<CurrentPath />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const loaded = (data: object[]) => ({ isPending: false, isError: false, data })

beforeEach(() => mutate.mockReset())

describe('simulation reports page', () => {
  it('asks for the reports of the simulation in the route', () => {
    renderPage(loaded([]))

    expect(useReports).toHaveBeenCalledWith({ simulationId: 4 })
    expect(useCreateReport).toHaveBeenCalledWith({ simulationId: 4 })
  })

  it('shows a skeleton, never the empty message, while the list is pending', () => {
    renderPage({ isPending: true, isError: false })

    expect(screen.getByRole('list', { name: 'Carregando relatórios' }).children).toHaveLength(3)
    expect(screen.queryByText('Nenhum relatório encontrado')).toBeNull()
    expect(screen.getByRole('button', { name: 'Gerar relatório' })).toBeTruthy()
  })

  it('keeps the generate button available on an empty list', () => {
    renderPage(loaded([]))

    expect(screen.getByText('Nenhum relatório encontrado')).toBeTruthy()
    const button = screen.getByRole('button', { name: 'Gerar relatório' }) as HTMLButtonElement
    expect(button.disabled).toBe(false)
  })

  it('opens exactly the report that was chosen', () => {
    renderPage(loaded([item(31, 'pronto'), item(29, 'pronto')]))

    expect(screen.getByRole('link', { name: 'Visualizar relatório 29' }).getAttribute('href')).toBe(
      '/simulacoes/4/relatorios/29',
    )
    expect(screen.getByRole('link', { name: 'Visualizar relatório 31' }).getAttribute('href')).toBe(
      '/simulacoes/4/relatorios/31',
    )
  })

  it('lists an unavailable report, with the API state, and gives no way to open it', () => {
    renderPage(loaded([item(31, 'pronto'), item(30, 'falhou')]))

    expect(screen.getByText('Relatório 30')).toBeTruthy()
    expect(screen.getByText('Falhou')).toBeTruthy()
    expect(
      (screen.getByRole('button', { name: 'Indisponível' }) as HTMLButtonElement).disabled,
    ).toBe(true)
    expect(screen.queryByRole('link', { name: 'Visualizar relatório 30' })).toBeNull()
    expect(screen.getAllByRole('link', { name: /Visualizar/ })).toHaveLength(1)
    expect(mutate).not.toHaveBeenCalled()
  })

  it('generates on click and ignores a second click before the first settles', () => {
    renderPage(loaded([item(31, 'pronto')]))
    const button = screen.getByRole('button', { name: 'Gerar relatório' })

    fireEvent.click(button)
    fireEvent.click(button)

    expect(mutate).toHaveBeenCalledTimes(1)
  })

  it('disables the button and says it is generating, without percentage', () => {
    renderPage(loaded([item(31, 'pronto')]), { isPending: true })

    const button = screen.getByRole('button', { name: 'Gerando relatório…' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(button.textContent).not.toMatch(/%/)
  })

  it('does not allow a second creation while a listed report is still "gerando"', () => {
    renderPage(loaded([item(32, 'gerando', { gerado_em: null })]))

    expect(
      (screen.getByRole('button', { name: 'Gerando relatório…' }) as HTMLButtonElement).disabled,
    ).toBe(true)
  })

  it('a failed generation shows the error, retries, and keeps the existing reports', () => {
    renderPage(loaded([item(31, 'pronto')]), {
      isError: true,
      error: new Error('já há um relatório em geração'),
    })

    expect(screen.getByRole('alert').textContent).toContain('Erro ao gerar relatório')
    expect(screen.getByText('Relatório 31')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(mutate).toHaveBeenCalledTimes(1)
  })

  it('a failed list shows the error and retries the list, not the creation', () => {
    const refetch = vi.fn()
    renderPage({ isPending: false, isError: true, error: new Error('rede'), refetch })

    expect(screen.getByRole('alert').textContent).toContain('Erro ao carregar relatórios: rede')
    expect(screen.queryByText('Nenhum relatório encontrado')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(refetch).toHaveBeenCalledTimes(1)
    expect(mutate).not.toHaveBeenCalled()
  })

  it('opens the new report right after it is created, without waiting on the list', () => {
    renderPage(loaded([item(31, 'pronto')]))

    fireEvent.click(screen.getByRole('button', { name: 'Gerar relatório' }))
    const [, options] = mutate.mock.calls[0] as [undefined, { onSuccess: (r: object) => void }]
    act(() => options.onSuccess({ id: 40, simulacao_id: 4, estado: 'gerando' }))

    expect(screen.getByTestId('path').textContent).toBe('/simulacoes/4/relatorios/40')
  })
})
