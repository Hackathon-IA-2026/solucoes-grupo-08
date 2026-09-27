import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCreateReport, useReports } from '../api/report'
import { ReportsDialog } from '../components/report/reports-dialog'

vi.mock('../api/report', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useReports: vi.fn(),
  useCreateReport: vi.fn(),
}))

afterEach(cleanup)

const report = (id: number, estado: string) => ({
  id,
  simulacao_id: 7,
  estado,
  gerado_em: '2026-09-23T22:05:00Z',
  revisoes_cobertas: [1, 2],
  revisoes_novas: [],
})

const mutate = vi.fn()

function renderDialog(open: boolean, data: object[] = []) {
  vi.mocked(useCreateReport).mockReturnValue({ mutate, isPending: false, isError: false } as never)
  vi.mocked(useReports).mockReturnValue({ isPending: false, isError: false, data } as never)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ReportsDialog open={open} onOpenChange={() => {}} simulationId={7} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('reports dialog', () => {
  it('lists the reports inside a dialog with a link to open each one', () => {
    renderDialog(true, [report(3, 'pronto')])

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Visualizar relatório 3' }).getAttribute('href')).toBe(
      '/simulacoes/7/relatorios/3',
    )
  })

  it('generates a new report from the dialog', () => {
    mutate.mockClear()
    renderDialog(true, [])

    fireEvent.click(screen.getByRole('button', { name: 'Gerar relatório' }))

    expect(mutate).toHaveBeenCalledTimes(1)
  })

  it('renders nothing while closed', () => {
    renderDialog(false)

    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
