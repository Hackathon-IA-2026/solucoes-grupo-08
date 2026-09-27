import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import type { RevisionListItem, SimulationListItem } from '../../../api/get-simulations'
import { RevisionsTable } from '../revisions-table'
import { TooltipProvider } from '@/components/ui/tooltip'

afterEach(cleanup)

function revision(
  id: number,
  position: number,
  current: boolean,
  whatChanged = 'Criada.',
): RevisionListItem {
  return {
    id,
    posicao: position,
    atual: current,
    criada_em: '2026-09-20T12:00:00Z',
    o_que_mudou: whatChanged,
    snapshot_id: '2026-09-21',
    metodo_versao: '0.5.1',
    periodo_inicio: '2025-09-01T00:00:00',
    periodo_fim: '2026-09-01T00:00:00',
    energia_recuperada_mwh: 62383,
    vpl_reais: 121581977,
    nota: null,
    procedencia: 'por_pessoa',
    revisao_anterior_id: null,
  }
}

function renderTable(revisions = [revision(20, 2, true), revision(10, 1, false)]) {
  const simulation = {
    id: 1,
    nome: 'Bateria 100 MW',
    restricao_id: 'R1',
    revisoes: revisions,
  } as SimulationListItem

  return render(
    <MemoryRouter>
      <TooltipProvider>
        <RevisionsTable simulation={simulation} />
      </TooltipProvider>
    </MemoryRouter>,
  )
}

describe('revisions table', () => {
  it('actions stay in a menu on the NPV column, closed until opened', () => {
    renderTable()

    expect(screen.queryByRole('link', { name: 'Abrir' })).toBeNull()
    expect(screen.queryByRole('menuitem', { name: 'Duplicar revisão' })).toBeNull()
    expect(screen.getAllByRole('button', { name: /Ações da revisão/ })).toHaveLength(2)
    expect(screen.getAllByText('R$ 121.581.977')).toHaveLength(2)
  })

  it('opens via keyboard, with the open and duplicate actions leading to the right places', () => {
    renderTable()

    fireEvent.keyDown(screen.getByRole('button', { name: 'Ações da revisão 2' }), {
      key: 'Enter',
    })

    expect(screen.getByRole('menuitem', { name: 'Abrir' }).getAttribute('href')).toBe(
      '/simulacoes/20',
    )
    expect(screen.getByRole('menuitem', { name: 'Duplicar revisão' }).getAttribute('href')).toBe(
      '/restricoes/R1/nova-simulacao?revisar=20',
    )
  })

  it('is a semantic table, with the horizontal scroll in its own container', () => {
    const { container } = renderTable()

    expect(screen.getByRole('table')).toBeTruthy()
    expect(screen.getAllByRole('columnheader')).toHaveLength(8)
    expect(screen.getAllByRole('row')).toHaveLength(3) // cabeçalho + 2 revisões
    expect((container.firstElementChild as HTMLElement).className).toContain('overflow-x-auto')
  })

  it('truncates "O que mudou" to one line and shows the full text in a tooltip on focus', async () => {
    const longText =
      'Reduziu a capacidade da bateria de 400 para 300 MWh e passou o cenário para conservador.'
    renderTable([revision(20, 1, true, longText)])

    const trigger = screen.getByText(longText)
    expect(trigger.className).toContain('truncate')
    expect(screen.queryByRole('tooltip')).toBeNull()

    fireEvent.focus(trigger)
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip.textContent).toBe(longText)
  })

  it('keeps the links to compare revisions', () => {
    renderTable()

    expect(screen.getByRole('link', { name: 'rev 2 contra rev 1' }).getAttribute('href')).toBe(
      '/comparar?a=20&b=10',
    )
  })
})
