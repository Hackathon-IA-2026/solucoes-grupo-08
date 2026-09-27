import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { reportFixture } from './report-fixture'
import SimulationReport from '../simulation-report'
import { useCreateReport, useReport, type Report } from '@/features/saved-simulations/api/report'
import { ProseText } from '@/features/saved-simulations/components/report/report-section'

vi.mock('@/features/saved-simulations/api/report', () => ({
  useReport: vi.fn(),
  useCreateReport: vi.fn(),
}))

afterEach(cleanup)

function mockReport(...args: Parameters<typeof reportFixture>) {
  mockData(reportFixture(...args))
}

function mockData(report: Report) {
  vi.mocked(useReport).mockReturnValue({
    isPending: false,
    isError: false,
    data: report,
  } as never)
  vi.mocked(useCreateReport).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as never)
}

function renderReport() {
  render(
    <MemoryRouter initialEntries={['/simulacoes/7/relatorios/1']}>
      <Routes>
        <Route
          path="/simulacoes/:simulacaoId/relatorios/:relatorioId"
          element={<SimulationReport />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('simulation report page', () => {
  it('shows a spinner while the report loads', () => {
    vi.mocked(useReport).mockReturnValue({ isPending: true, isError: false } as never)
    vi.mocked(useCreateReport).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
    renderReport()

    expect(screen.getByRole('status').textContent).toContain('Carregando seu relatório')
  })

  it('shows the API error when the report fails to load', () => {
    vi.mocked(useReport).mockReturnValue({
      isPending: false,
      isError: true,
      error: new Error('não existe'),
    } as never)
    vi.mocked(useCreateReport).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
    renderReport()

    expect(screen.getByText(/não existe/).textContent).toContain('não existe')
  })

  it('shows the model prose and the code-derived blocks when "pronto"', () => {
    mockReport('pronto')
    renderReport()

    expect(screen.getByText('Pronto')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Leitura geral' })).toBeTruthy()
    expect(
      screen.getByRole('tab', { name: 'Ranking por métrica' }).getAttribute('aria-selected'),
    ).toBe('true')
    expect(screen.getByText('2 revisões novas')).toBeTruthy()
  })

  it('hides the prose and shows the failing number when "barrado"', () => {
    mockReport('barrado')
    renderReport()

    expect(screen.queryByRole('heading', { name: 'Leitura geral' })).toBeNull()
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toContain('Prosa barrada pela verificação')
    expect(alert.textContent).toContain('R$ 512 mil')
  })

  it('shows nothing but the loader while "gerando": no header, no buttons, no blocks', () => {
    mockReport('gerando')
    renderReport()

    expect(screen.getByRole('status').textContent).toContain('Gerando seu relatório')
    expect(screen.queryByRole('heading', { name: 'Relatório da simulação' })).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.queryByRole('tablist')).toBeNull()
  })

  it('swaps the whole page for the loader from the click on the new report button', () => {
    mockReport('pronto')
    vi.mocked(useCreateReport).mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      isSuccess: false,
      isError: false,
    } as never)
    renderReport()

    expect(screen.getByRole('status').textContent).toContain('Gerando seu relatório')
    expect(screen.queryByRole('heading', { name: 'Relatório da simulação' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Gerar relatório novo' })).toBeNull()
  })

  it('shows the error when "falhou"', () => {
    mockReport('falhou')
    renderReport()

    expect(screen.getByRole('alert').textContent).toContain('A geração falhou')
  })

  it('links each covered revision to its own screen', () => {
    mockReport('pronto')
    renderReport()

    const trail = screen.getByRole('heading', { name: 'Trilha da exploração' }).closest('article')!
    expect(within(trail).getByRole('link', { name: 'rev 3' }).getAttribute('href')).toBe(
      '/simulacoes/103',
    )
  })
})

describe('report layout', () => {
  function withFields(extra: { campo: string; rotulo: string; valor: string }[]) {
    const report = reportFixture('pronto')
    return {
      ...report,
      derivados: {
        ...report.derivados!,
        ficou_parado: [...report.derivados!.ficou_parado, ...extra],
      },
    }
  }

  it('switches the comparison between "Ranking por métrica", "Diferenças vs base e anterior" and "Sensibilidade observada"', () => {
    mockReport('pronto')
    renderReport()

    fireEvent.click(screen.getByRole('tab', { name: 'Diferenças vs base e anterior' }))

    expect(
      screen
        .getByRole('tab', { name: 'Diferenças vs base e anterior' })
        .getAttribute('aria-selected'),
    ).toBe('true')
    const panel = screen.getByRole('tabpanel')
    expect(within(panel).getByRole('columnheader', { name: 'O que mudou' })).toBeTruthy()
  })

  it('moves between tabs with the arrow keys', () => {
    mockReport('pronto')
    renderReport()

    fireEvent.keyDown(screen.getByRole('tab', { name: 'Ranking por métrica' }), {
      key: 'ArrowLeft',
    })

    expect(document.activeElement?.textContent).toBe('Sensibilidade observada')
  })

  it('with a single revision, shows one empty state that links to "Criar nova revisão"', () => {
    const report = reportFixture('pronto')
    mockData({ ...report, por_revisao: report.por_revisao.slice(0, 1) })
    renderReport()

    expect(screen.queryByRole('tablist')).toBeNull()
    const cta = screen.getByRole('link', { name: 'Criar nova revisão' })
    expect(cta.getAttribute('href')).toBe(
      `/restricoes/exemplo/nova-simulacao?revisar=${report.por_revisao[0].revisao_id}`,
    )
  })

  it('warns when the initial investment looks like a typo, and not otherwise', () => {
    mockData(
      withFields([
        { campo: 'financeira.capex_reais', rotulo: 'Investimento inicial', valor: 'R$ 0,42' },
      ]),
    )
    renderReport()
    expect(screen.getByText(/Investimento inicial registrado de/).textContent).toContain('R$ 0,42')
    cleanup()

    mockData(
      withFields([
        { campo: 'financeira.capex_reais', rotulo: 'Investimento inicial', valor: 'R$ 250.000' },
      ]),
    )
    renderReport()
    expect(screen.queryByText(/Investimento inicial registrado de/)).toBeNull()
  })

  it('groups the configuration by battery, operation and financial, marking what varied', () => {
    mockData(
      withFields([
        { campo: 'financeira.taxa_desconto_aa', rotulo: 'Taxa de desconto', valor: '0,08 ao ano' },
      ]),
    )
    renderReport()

    const battery = screen.getByRole('heading', { name: 'Bateria', level: 4 }).parentElement!
    expect(within(battery).getByText('Ponto de conexão')).toBeTruthy()
    expect(within(battery).getByText('variou')).toBeTruthy()
    const financial = screen.getByRole('heading', { name: 'Financeiro', level: 4 }).parentElement!
    expect(within(financial).getByText('0,08 ao ano')).toBeTruthy()
  })
})

describe('prose text', () => {
  it('highlights numbers with unit and leaves the sentence period out', () => {
    const { container } = render(
      <ProseText text="Subiu 3.400 MWh, com custo em R$ 540. A fração foi de 6,4 %, versão v0.7.0." />,
    )

    const highlighted = [...container.querySelectorAll('span')].map((span) => span.textContent)
    expect(highlighted).toEqual(['3.400 MWh', 'R$ 540', '6,4 %'])
  })
})

describe('removed cards', () => {
  it('does not show the fixed disclaimers card nor the verification card', () => {
    mockReport('pronto')
    renderReport()

    expect(screen.queryByRole('heading', { name: 'O que este relatório não afirma' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Verificação' })).toBeNull()
  })
})

describe('loading until the last step', () => {
  afterEach(() => vi.useRealTimers())

  function mockFetchState(state: 'pending' | 'done') {
    vi.mocked(useReport).mockReturnValue({
      isPending: state === 'pending',
      isError: false,
      data: state === 'done' ? reportFixture('pronto') : undefined,
    } as never)
    vi.mocked(useCreateReport).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
  }

  function tree(state?: object) {
    return (
      <MemoryRouter
        initialEntries={[{ pathname: '/simulacoes/7/relatorios/1', state: state ?? null }]}
      >
        <Routes>
          <Route
            path="/simulacoes/:simulacaoId/relatorios/:relatorioId"
            element={<SimulationReport />}
          />
        </Routes>
      </MemoryRouter>
    )
  }

  it('renders at once when the report is already in the cache', () => {
    mockFetchState('done')
    render(tree())

    expect(screen.getByRole('heading', { name: 'Leitura geral' })).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  function advanceSteps(count: number) {
    for (let step = 0; step < count; step++) act(() => void vi.advanceTimersByTime(2_500))
  }

  it('opened by the URL with the report already "pronto", shows it as soon as the API answers', () => {
    vi.useFakeTimers()
    mockFetchState('pending')
    const { rerender } = render(tree())
    expect(screen.getByRole('status')).toBeTruthy()

    mockFetchState('done')
    rerender(tree())

    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Leitura geral' })).toBeTruthy()
  })

  it('after following a "gerando" report, shows it only once the loading reaches the last step', () => {
    vi.useFakeTimers()
    mockData(reportFixture('gerando'))
    const { rerender } = render(tree())

    mockFetchState('done')
    rerender(tree())
    advanceSteps(2)
    expect(screen.getByRole('status')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Leitura geral' })).toBeNull()

    advanceSteps(1)
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Leitura geral' })).toBeTruthy()
  })

  it('opened already generated from the list ("Visualizar"), skips the loading steps', () => {
    vi.useFakeTimers()
    mockFetchState('pending')
    const { rerender } = render(tree({ generated: true }))
    expect(screen.queryByText('Carregando seu relatório')).toBeNull()

    mockFetchState('done')
    rerender(tree({ generated: true }))

    expect(screen.getByRole('heading', { name: 'Leitura geral' })).toBeTruthy()
  })

  it('keeps waiting on the last step while the API has not answered', () => {
    vi.useFakeTimers()
    mockFetchState('pending')
    render(tree())

    advanceSteps(20)

    expect(screen.getByRole('status').textContent).toContain('Finalizando relatório')
  })
})
