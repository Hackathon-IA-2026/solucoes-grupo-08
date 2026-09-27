import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCreateTask, useTasks } from '../api/exploration'
import { ExplorationsDialog } from '../components/explorations-dialog'

vi.mock('../api/exploration', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useTasks: vi.fn(),
  useCreateTask: vi.fn(),
}))

afterEach(cleanup)

const task = (id: number, estado: string) => ({
  id,
  simulacao_id: 7,
  estado,
  pedido: `pedido ${id}`,
  teto: 30,
  revisao_partida_id: 18,
  criada_em: '2026-09-23T22:05:00Z',
  contagem: {
    rodadas: 1,
    disparadas: 1,
    trabalhando: 0,
    prontas: 1,
    recusadas: 0,
    interrompidas: 0,
  },
  motivo: null,
  erro: null,
  relatorio_id: null,
})

const mutate = vi.fn()

function renderDialog(open: boolean, data: object[] = []) {
  vi.mocked(useCreateTask).mockReturnValue({ mutate, isError: false, isPending: false } as never)
  vi.mocked(useTasks).mockReturnValue({ isPending: false, isError: false, data } as never)
  render(
    <MemoryRouter>
      <ExplorationsDialog open={open} onOpenChange={() => {}} simulationId={7} revisionId={18} />
    </MemoryRouter>,
  )
}

describe('explorations dialog', () => {
  it('lists the explorations inside a dialog and offers a new one', () => {
    renderDialog(true, [task(3, 'concluida')])

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('pedido 3')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Abrir exploração 3' }).textContent).toBe('Abrir')
    expect(screen.queryByText('Ver processamento')).toBeNull()
    expect(screen.getByRole('button', { name: 'Nova exploração' })).toBeTruthy()
  })

  it('"Nova exploração" shows only a textarea and sends the request and the revision', () => {
    mutate.mockClear()
    renderDialog(true, [task(3, 'concluida')])

    fireEvent.click(screen.getByRole('button', { name: 'Nova exploração' }))
    expect(screen.queryByText('pedido 3')).toBeNull()
    const start = screen.getByRole('button', { name: 'Começar a exploração' })
    expect((start as HTMLButtonElement).disabled).toBe(true)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  variar a bateria  ' } })
    fireEvent.click(start)

    expect(mutate).toHaveBeenCalledTimes(1)
    expect(mutate.mock.calls[0][0]).toEqual({ pedido: 'variar a bateria', revisao_partida_id: 18 })
  })

  it('"Cancelar" goes back to the list', () => {
    renderDialog(true, [task(3, 'concluida')])

    fireEvent.click(screen.getByRole('button', { name: 'Nova exploração' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(screen.getByText('pedido 3')).toBeTruthy()
  })

  it('has no report button, even when the exploration has a report', () => {
    renderDialog(true, [{ ...task(5, 'concluida'), relatorio_id: 9 }])

    expect(screen.queryByRole('link', { name: 'Relatório' })).toBeNull()
  })

  it('points to the running exploration instead of starting another', () => {
    renderDialog(true, [task(4, 'em_andamento')])

    expect(
      screen.getByRole('link', { name: 'Acompanhar a exploração 4' }).getAttribute('href'),
    ).toBe('/simulacoes/7/exploracoes/4')
    expect(screen.queryByRole('button', { name: 'Nova exploração' })).toBeNull()
  })

  it('renders nothing while closed', () => {
    renderDialog(false)
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
