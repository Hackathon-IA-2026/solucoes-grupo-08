import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Occurrence, RestrictionOccurrences } from '../../api/get-restriction-occurrences'
import { useRestrictionOccurrences } from '../../api/get-restriction-occurrences'
import { RestrictionOccurrencesTable } from '../restriction-occurrences-table'
import { TooltipProvider } from '@/components/ui/tooltip'

vi.mock('../../api/get-restriction-occurrences', () => ({ useRestrictionOccurrences: vi.fn() }))

afterEach(cleanup)

const AVISO = 'A contagem é sensível a artefato de apuração. Serve para auditoria.'

function occurrence(index: number): Occurrence {
  return {
    inicio: `2025-10-${String(index + 1).padStart(2, '0')}T15:00:00`,
    fim: `2025-10-${String(index + 1).padStart(2, '0')}T17:30:00`,
    intervalos: 5,
    duracao_horas: 2.5,
    energia_mwh: 1000 - index,
    corte_medio_maximo_mw: 250.75,
  }
}

function data(count: number): RestrictionOccurrences {
  return {
    restricao_id: 'R1',
    snapshot_id: '2026-09-21',
    fonte: 'eolica',
    total: count,
    energia_mwh: 5000,
    aviso: AVISO,
    itens: Array.from({ length: count }, (_, index) => occurrence(index)),
  }
}

function mockQuery(state: Record<string, unknown>) {
  vi.mocked(useRestrictionOccurrences).mockReturnValue(state as never)
}

function renderTable() {
  render(
    <TooltipProvider>
      <RestrictionOccurrencesTable restrictionId="R1" source="eolica" />
    </TooltipProvider>,
  )
}

describe('occurrences table', () => {
  it('requests the restriction and the source from the screen', () => {
    mockQuery({ isPending: true, isError: false })
    renderTable()

    expect(useRestrictionOccurrences).toHaveBeenCalledWith({
      restrictionId: 'R1',
      source: 'eolica',
    })
  })

  it('shows loading without asserting anything', () => {
    mockQuery({ isPending: true, isError: false })
    renderTable()

    expect(screen.getByRole('heading', { name: 'Ocorrências' })).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('shows the error and allows retrying', () => {
    const refetch = vi.fn()
    mockQuery({ isPending: false, isError: true, error: new Error('API fora do ar'), refetch })
    renderTable()

    expect(
      screen.getByText(/Não foi possível carregar as ocorrências: API fora do ar/),
    ).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(refetch).toHaveBeenCalled()
  })

  it('with no occurrence, says so and keeps the warning', () => {
    mockQuery({ isPending: false, isError: false, data: data(0) })
    renderTable()

    expect(screen.getByText(/Sem ocorrência de corte nesta fonte/)).toBeTruthy()
    expect(screen.getByRole('note').textContent).toBe(AVISO)
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('shows the API warning next to the number, the total and the energy', () => {
    mockQuery({ isPending: false, isError: false, data: data(3) })
    renderTable()

    expect(screen.getByRole('note').textContent).toBe(AVISO)
    expect(screen.getByText(/3 ocorrências no período, 5,0 GWh cortados/)).toBeTruthy()
  })

  it('writes the rows with what the API sent, in the order it came', () => {
    mockQuery({ isPending: false, isError: false, data: data(3) })
    renderTable()

    const rows = screen.getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    const cells = [...rows[0].querySelectorAll('td')].map((cell) => cell.textContent)
    expect(cells.slice(2)).toEqual(['2,5', '5', '1.000,0', '250,8'])
    expect(rows[1].querySelectorAll('td')[4].textContent).toBe('999,0')
  })

  it('shows 20 at a time and releases more on demand', () => {
    mockQuery({ isPending: false, isError: false, data: data(45) })
    renderTable()

    expect(screen.getAllByRole('row')).toHaveLength(21)
    expect(screen.getByText(/Mostrando 20 de 45/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Mostrar mais' }))
    expect(screen.getAllByRole('row')).toHaveLength(41)

    fireEvent.click(screen.getByRole('button', { name: 'Mostrar mais' }))
    expect(screen.getAllByRole('row')).toHaveLength(46)
    expect(screen.queryByRole('button', { name: 'Mostrar mais' })).toBeNull()
  })

  it('uses the singular form for a single occurrence', () => {
    mockQuery({ isPending: false, isError: false, data: data(1) })
    renderTable()

    expect(screen.getByText(/1 ocorrência no período/)).toBeTruthy()
  })
})
