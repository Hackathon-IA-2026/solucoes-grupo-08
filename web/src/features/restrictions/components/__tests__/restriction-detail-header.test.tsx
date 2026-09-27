import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import { RestrictionDetailHeader } from '../restriction-detail-header'
import { TooltipProvider } from '@/components/ui/tooltip'

afterEach(cleanup)

function renderHeader() {
  const item = {
    id: 'R1',
    texto: 'LT 500 kV ALFA / BETA C1',
    nome_curto: 'LT 500 kV ALFA / BETA C1',
    origem: 'LOC',
    razao: 'CNF',
    fonte: 'eolica',
    instrucao_operacao: 'IO-ON.NE.5NE',
  }

  return render(
    <MemoryRouter>
      <TooltipProvider>
        <RestrictionDetailHeader item={item as never} />
      </TooltipProvider>
    </MemoryRouter>,
  )
}

describe('restriction detail header', () => {
  it('explains "origem: LOC" in a tooltip on the acronym', async () => {
    renderHeader()

    fireEvent.focus(screen.getByRole('button', { name: 'Ajuda: origem' }))
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip.textContent).toContain('LOC é local')
  })

  it('the simulations button links to the list already filtered by this restriction', () => {
    renderHeader()

    const link = screen.getByRole('link', { name: 'Ver simulações' })
    expect(link.getAttribute('href')).toBe(
      '/simulacoes?restricao=R1&nome=LT+500+kV+ALFA+%2F+BETA+C1',
    )
  })
})
