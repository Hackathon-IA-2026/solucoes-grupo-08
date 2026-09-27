import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import { CompareColumns } from '../compare-columns'
import { TooltipProvider } from '@/components/ui/tooltip'

afterEach(cleanup)

function revision(id: number, snapshotId: string) {
  return {
    id,
    nome: 'Bateria 100 MW',
    criada_em: '2026-09-20T12:00:00Z',
    snapshot_id: snapshotId,
    metodo_versao: '0.5.1',
    periodo_inicio: '2025-09-01T00:00:00',
    periodo_fim: '2026-09-01T00:00:00',
    revisoes: [{ id, posicao: 1, atual: true }],
  }
}

describe('compare columns', () => {
  it('explains the ONS snapshot and method version in tooltips, same text as the result header', async () => {
    render(
      <MemoryRouter>
        <TooltipProvider>
          <CompareColumns
            a={revision(1, '2026-09-21') as never}
            b={revision(2, '2026-08-21') as never}
          />
        </TooltipProvider>
      </MemoryRouter>,
    )

    fireEvent.focus(screen.getAllByRole('button', { name: 'Ajuda: ONS versão' })[0])
    expect((await screen.findByRole('tooltip')).textContent).toContain('Snapshot')
  })
})
