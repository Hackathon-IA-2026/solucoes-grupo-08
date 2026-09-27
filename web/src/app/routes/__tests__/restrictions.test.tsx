import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Restrictions from '../restrictions'
import { useRestrictions } from '@/features/restrictions/api/get-restrictions'
import { useSnapshot } from '@/features/snapshot/api/get-snapshot'
import { TooltipProvider } from '@/components/ui/tooltip'

vi.mock('@/features/restrictions/api/get-restrictions', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useRestrictions: vi.fn(),
}))
vi.mock('@/features/snapshot/api/get-snapshot', () => ({ useSnapshot: vi.fn() }))

afterEach(cleanup)

const AVISO = 'A contagem de ocorrências é sensível a artefato de apuração.'

function item(id: string, texto: string) {
  return {
    posicao: 1,
    id,
    texto,
    nome_curto: null,
    contingencia: null,
    instrucao_operacao: null,
    energia_mwh: 1000,
    fatia_do_total: 0.5,
    equipamentos: 1,
    subestacoes: ['ALFA'],
    snapshot_id: '2026-09-21',
    ocorrencias: 12,
  }
}

function renderPage(itens: ReturnType<typeof item>[]) {
  vi.mocked(useRestrictions).mockReturnValue({
    isPending: false,
    isError: false,
    data: {
      resumo: {
        fonte: 'eolica',
        snapshot_id: '2026-09-21',
        restricoes: itens.length,
        energia_mwh: 2000,
        aviso_ocorrencias: AVISO,
      },
      itens,
    },
  } as never)
  vi.mocked(useSnapshot).mockReturnValue({ data: undefined } as never)

  render(
    <MemoryRouter>
      <TooltipProvider>
        <Restrictions />
      </TooltipProvider>
    </MemoryRouter>,
  )
}

describe('restrictions list, occurrences warning', () => {
  it('shows the API warning next to the Occurrences column', () => {
    renderPage([item('a', 'LT ALFA'), item('b', 'LT BETA')])

    expect(screen.getByRole('note').textContent).toBe(AVISO)
    expect(screen.getByRole('columnheader', { name: 'Ocorrências' })).toBeTruthy()
  })

  it('disappears when the search leaves no row with the number', () => {
    renderPage([item('a', 'LT ALFA')])

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'nada disso' } })

    expect(screen.queryByRole('note')).toBeNull()
  })

  it('does not appear with no restriction in the list', () => {
    renderPage([])

    expect(screen.queryByRole('note')).toBeNull()
  })
})

describe('restrictions list, tooltips', () => {
  it('opens the API warning as a tooltip on the occurrences header', async () => {
    renderPage([item('a', 'LT ALFA')])

    fireEvent.focus(screen.getByText('Ocorrências', { selector: 'span' }))
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip.textContent).toBe(AVISO)
  })
})
