import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RestrictionPickerDialog } from '../restriction-picker-dialog'
import { useRestrictions } from '@/features/restrictions/api/get-restrictions'

vi.mock('@/features/restrictions/api/get-restrictions', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useRestrictions: vi.fn(),
}))

afterEach(cleanup)

function item(id: string, nome_curto: string, subestacoes: string[]) {
  return {
    posicao: 1,
    id,
    texto: nome_curto,
    nome_curto,
    contingencia: null,
    instrucao_operacao: null,
    energia_mwh: 1000,
    fatia_do_total: 0.5,
    equipamentos: 1,
    subestacoes,
    snapshot_id: '2026-09-21',
    ocorrencias: 12,
  }
}

function CurrentPath() {
  return <p data-testid="path">{useLocation().pathname}</p>
}

function renderDialog() {
  vi.mocked(useRestrictions).mockReturnValue({
    isPending: false,
    isError: false,
    data: {
      resumo: {},
      itens: [item('a', 'LT ALFA', ['ALFA', 'GAMA']), item('b', 'LT BETA', ['BETA'])],
    },
  } as never)

  render(
    <MemoryRouter initialEntries={['/restricoes/a/nova-simulacao']}>
      <Routes>
        <Route
          path="/restricoes/:id/nova-simulacao"
          element={
            <>
              <RestrictionPickerDialog currentRestrictionId="a" />
              <CurrentPath />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Trocar de restrição' }))
}

describe('restriction picker dialog', () => {
  it('lists the restrictions in a modal and marks the current one', () => {
    renderDialog()

    expect(screen.getByRole('dialog', { name: 'Trocar de restrição' })).toBeTruthy()
    const current = screen.getByRole('button', { current: true })
    expect(current.textContent).toContain('LT ALFA')
    expect(current.textContent).toContain('atual')
  })

  it('filters by substation', () => {
    renderDialog()

    fireEvent.change(screen.getByRole('textbox', { name: 'Buscar restrição' }), {
      target: { value: 'beta' },
    })

    expect(screen.queryByText('LT ALFA')).toBeNull()
    expect(screen.getByText('LT BETA')).toBeTruthy()
  })

  it('choosing another restriction swaps only the route and closes the modal', () => {
    renderDialog()

    fireEvent.click(screen.getByText('LT BETA'))

    expect(screen.getByTestId('path').textContent).toBe('/restricoes/b/nova-simulacao')
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
