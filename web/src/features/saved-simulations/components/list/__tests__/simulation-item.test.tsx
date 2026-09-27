import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import type { SimulationListItem } from '../../../api/get-simulations'
import { SimulationItem } from '../simulation-item'
import { TooltipProvider } from '@/components/ui/tooltip'

afterEach(cleanup)

const simulation = {
  id: 1,
  nome: 'Bateria 100 MW',
  modalidade: 'bateria',
  restricao_id: 'R1',
  revisoes: [
    {
      id: 10,
      posicao: 1,
      atual: false,
      periodo_inicio: '2025-09-01T00:00:00',
      periodo_fim: '2026-09-01T00:00:00',
    },
    {
      id: 20,
      posicao: 2,
      atual: true,
      periodo_inicio: '2025-09-01T00:00:00',
      periodo_fim: '2026-09-01T00:00:00',
    },
  ],
} as unknown as SimulationListItem

function renderItem() {
  render(
    <MemoryRouter>
      <TooltipProvider>
        <SimulationItem
          simulation={simulation}
          selected={false}
          onSelectedChange={() => {}}
          expanded={false}
          onToggle={() => {}}
          outdated={false}
        />
      </TooltipProvider>
    </MemoryRouter>,
  )
}

describe('simulation item', () => {
  it('has an Abrir button at the end of the header, going to the current revision', () => {
    renderItem()

    expect(screen.getByRole('link', { name: 'Abrir Bateria 100 MW' }).getAttribute('href')).toBe(
      '/simulacoes/20',
    )
  })

  it('puts the name before the modality badge, and does not repeat the period', () => {
    renderItem()

    const title = screen.getByRole('link', { name: 'Bateria 100 MW' })
    const badge = screen.getByText('Bateria', { selector: 'span' })
    expect(title.compareDocumentPosition(badge) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByText(/a ago\\. de 2026/)).toBeNull()
  })
})
