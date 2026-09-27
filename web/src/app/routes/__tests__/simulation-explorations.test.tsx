import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SimulationExplorations from '../simulation-explorations'
import { useTasks } from '@/features/agents/api/exploration'

vi.mock('@/features/agents/api/exploration', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useTasks: vi.fn(),
}))

vi.mock('@/features/saved-simulations/api/simulation-crumb', () => ({
  useSimulationCrumb: (_simulationId: number, revision?: number) => ({
    label: 'Bateria 300 MW',
    to: `/simulacoes/${revision ?? 99}`,
  }),
}))

afterEach(cleanup)

const counts = {
  rodadas: 2,
  disparadas: 5,
  trabalhando: 0,
  prontas: 4,
  recusadas: 1,
  interrompidas: 0,
}
const task = (id: number, estado: string, extra: object = {}) => ({
  id,
  simulacao_id: 7,
  estado,
  pedido: `pedido ${id}`,
  teto: 30,
  revisao_partida_id: 18,
  criada_em: '2026-09-23T22:05:00Z',
  contagem: counts,
  motivo: null,
  erro: null,
  relatorio_id: null,
  ...extra,
})

function renderList(result: object, url = '/simulacoes/7/exploracoes?revisao=18') {
  vi.mocked(useTasks).mockReturnValue(result as never)
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/simulacoes/:simulacaoId/exploracoes" element={<SimulationExplorations />} />
      </Routes>
    </MemoryRouter>,
  )
}

const href = (name: string) => screen.getByRole('link', { name }).getAttribute('href')

describe('explorations list', () => {
  it('lists each exploration with its request and a link to follow it', () => {
    renderList({
      isPending: false,
      isError: false,
      data: [
        task(9, 'concluida', { relatorio_id: 3, motivo: 'cobriu a faixa' }),
        task(8, 'falhou', { erro: 'modelo caiu' }),
      ],
    })

    expect(screen.getByText('pedido 9')).toBeTruthy()
    expect(screen.getByText('cobriu a faixa')).toBeTruthy()
    expect(screen.getByText('modelo caiu')).toBeTruthy()
    expect(screen.getByText('Concluída')).toBeTruthy()
    expect(href('Ver processamento da exploração 9')).toBe('/simulacoes/7/exploracoes/9')
    expect(href('Relatório')).toBe('/simulacoes/7/relatorios/3')
  })

  it('offers "Nova exploração" from the revision the person came from', () => {
    renderList({ isPending: false, isError: false, data: [task(9, 'concluida')] })

    expect(screen.getByRole('button', { name: 'Nova exploração' })).toBeTruthy()
    const trail = screen.getByRole('navigation', { name: 'Trilha de navegação' })
    expect(trail.textContent).toBe('Simulações/Bateria 300 MW/Explorações')
    expect(href('Bateria 300 MW')).toBe('/simulacoes/18')
  })

  it('with one running, points to it instead of offering a new one', () => {
    renderList({ isPending: false, isError: false, data: [task(9, 'em_andamento')] })

    expect(screen.queryByRole('button', { name: 'Nova exploração' })).toBeNull()
    expect(href('Acompanhar a exploração 9')).toBe('/simulacoes/7/exploracoes/9')
  })

  it('says when there is none yet', () => {
    renderList({ isPending: false, isError: false, data: [] })

    expect(screen.getByText('Nenhuma exploração nesta simulação')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Começar a primeira' })).toBeTruthy()
  })

  it('shows the error when the list does not load', () => {
    renderList({
      isPending: false,
      isError: true,
      error: new Error('fora do ar'),
      refetch: vi.fn(),
    })

    expect(screen.getByRole('alert').textContent).toContain('fora do ar')
  })
})
