import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Simulations from '../simulations'
import { useSimulations } from '@/features/saved-simulations/api/get-simulations'
import { useRestrictions } from '@/features/restrictions/api/get-restrictions'
import { useSnapshot } from '@/features/snapshot/api/get-snapshot'
import { TooltipProvider } from '@/components/ui/tooltip'

vi.mock('@/features/saved-simulations/api/get-simulations', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useSimulations: vi.fn(),
}))
vi.mock('@/features/restrictions/api/get-restrictions', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useRestrictions: vi.fn(),
}))
vi.mock('@/features/snapshot/api/get-snapshot', () => ({ useSnapshot: vi.fn() }))

afterEach(cleanup)

function revision(id: number) {
  return {
    id,
    posicao: 1,
    atual: true,
    criada_em: '2026-09-20T12:00:00Z',
    snapshot_id: '2026-09-21',
    metodo_versao: '0.7.0',
    periodo_inicio: '2025-09-01T00:00:00',
    periodo_fim: '2026-09-01T00:00:00',
    energia_recuperada_mwh: 1000,
    vpl_reais: 1_000_000,
    o_que_mudou: 'base',
  }
}

function simulation(id: number, restricaoId: string, restricaoTexto: string | null) {
  return {
    id,
    nome: `Simulação ${id}`,
    pergunta: null,
    modalidade: 'bateria',
    restricao_id: restricaoId,
    restricao_texto: restricaoTexto,
    criada_em: '2026-09-20T12:00:00Z',
    revisoes: [revision(id * 10)],
  }
}

function CurrentPath() {
  return <p data-testid="path">{useLocation().pathname}</p>
}

function CurrentSearch() {
  return <p data-testid="search">{decodeURIComponent(useLocation().search)}</p>
}

function renderPage(url: string) {
  vi.mocked(useSimulations).mockReturnValue({
    isPending: false,
    isError: false,
    data: [
      simulation(1, 'R1', 'LT 500 kV ALFA / BETA C1'),
      simulation(2, 'R2', 'LT 230 kV GAMA / DELTA C1'),
    ],
  } as never)
  vi.mocked(useSnapshot).mockReturnValue({ data: undefined } as never)
  vi.mocked(useRestrictions).mockReturnValue({
    isPending: false,
    isError: false,
    data: {
      resumo: {},
      itens: [
        {
          id: 'R1',
          posicao: 1,
          texto: 'LT 500 kV ALFA / BETA C1',
          nome_curto: null,
          energia_mwh: 1000,
          equipamentos: 1,
          subestacoes: ['ALFA'],
        },
      ],
    },
  } as never)

  render(
    <MemoryRouter initialEntries={[url]}>
      <TooltipProvider>
        <Routes>
          <Route
            path="/simulacoes"
            element={
              <>
                <Simulations />
                <CurrentSearch />
              </>
            }
          />
          <Route path="/restricoes/:id/nova-simulacao" element={<CurrentPath />} />
        </Routes>
      </TooltipProvider>
    </MemoryRouter>,
  )
}

describe('simulations page', () => {
  it('shows every simulation without a filter in the URL', () => {
    renderPage('/simulacoes')

    expect(screen.getByText('Simulação 1')).toBeTruthy()
    expect(screen.getByText('Simulação 2')).toBeTruthy()
  })

  it('the restriction query param pre-filters the list to that restriction', () => {
    renderPage('/simulacoes?restricao=R1&nome=LT+500+kV+ALFA+%2F+BETA+C1')

    expect(screen.getByText('Simulação 1')).toBeTruthy()
    expect(screen.queryByText('Simulação 2')).toBeNull()
    expect(screen.getByRole('combobox', { name: 'Restrição' }).textContent).toContain(
      'LT 500 kV ALFA / BETA C1',
    )
  })

  it('pre-selects a restriction that has no saved simulation yet, by the name in the URL', () => {
    renderPage('/simulacoes?restricao=R9&nome=LT+500+kV+NOVA+RESTRIÇÃO')

    expect(screen.getByText('Nenhuma simulação encontrada para este filtro.')).toBeTruthy()
    expect(screen.getByRole('combobox', { name: 'Restrição' }).textContent).toContain(
      'LT 500 kV NOVA RESTRIÇÃO',
    )
  })

  it('the new simulation button opens the restriction picker, and choosing one starts its simulation', () => {
    renderPage('/simulacoes')

    fireEvent.click(screen.getByRole('button', { name: 'Nova simulação' }))
    const dialog = screen.getByRole('dialog', { name: 'Nova simulação' })

    fireEvent.click(within(dialog).getByText('LT 500 kV ALFA / BETA C1'))

    expect(screen.getByTestId('path').textContent).toBe('/restricoes/R1/nova-simulacao')
  })

  it('writes the chosen restriction to the URL, replacing the one it arrived with', () => {
    renderPage('/simulacoes?restricao=R1&nome=LT+500+kV+ALFA+%2F+BETA+C1')

    fireEvent.change(screen.getByRole('combobox', { name: 'Restrição' }), {
      target: { value: 'R2' },
    })

    const search = screen.getByTestId('search').textContent
    expect(search).toContain('restricao=R2')
    expect(search).toContain('nome=LT+230+kV+GAMA+/+DELTA+C1')
    expect(screen.queryByText('Simulação 1')).toBeNull()
    expect(screen.getByText('Simulação 2')).toBeTruthy()
  })

  it('choosing "Todas" clears the restriction from the URL', () => {
    renderPage('/simulacoes?restricao=R1&nome=LT+500+kV+ALFA+%2F+BETA+C1')

    fireEvent.change(screen.getByRole('combobox', { name: 'Restrição' }), {
      target: { value: 'todas' },
    })

    expect(screen.getByTestId('search').textContent).toBe('')
    expect(screen.getByText('Simulação 1')).toBeTruthy()
    expect(screen.getByText('Simulação 2')).toBeTruthy()
  })
})
