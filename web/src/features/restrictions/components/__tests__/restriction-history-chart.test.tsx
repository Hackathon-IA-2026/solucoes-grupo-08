import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  RestrictionHistoryChart,
  digitsIn,
  fitsLabelPerBar,
  shouldShowBarLabel,
  tickLabel,
} from '../restriction-history-chart'
import { useRestrictionSeries } from '../../api/get-restriction-series'

vi.mock('../../api/get-restriction-series', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useRestrictionSeries: vi.fn(),
}))

afterEach(cleanup)

function bucket(inicio: string, energiaMwh: number) {
  return { inicio, energia_mwh: energiaMwh }
}

function mockSeries(state: {
  isPending?: boolean
  isError?: boolean
  error?: Error
  data?: { baldes: ReturnType<typeof bucket>[] }
}) {
  vi.mocked(useRestrictionSeries).mockReturnValue({
    isPending: false,
    isError: false,
    data: undefined,
    ...state,
  } as never)
}

function renderChart() {
  return render(<RestrictionHistoryChart restrictionId="R1" source="eolica" />)
}

// A geometria do `recharts` (largura e posição de cada barra) só existe com layout de
// verdade, que o jsdom não faz: quem carrega a cobertura de "número em toda barra que couber"
// é a regra pura abaixo, não o SVG renderizado. Ver `restriction-history-chart.tsx`.
describe('shouldShowBarLabel', () => {
  it('shows every bar when the series fits', () => {
    for (let index = 0; index < 12; index++) {
      expect(shouldShowBarLabel(index, 12, true)).toBe(true)
    }
  })

  it('shows only the first and the last bar when the series is dense', () => {
    expect(shouldShowBarLabel(0, 300, false)).toBe(true)
    expect(shouldShowBarLabel(150, 300, false)).toBe(false)
    expect(shouldShowBarLabel(299, 300, false)).toBe(true)
  })
})

describe('digitsIn', () => {
  it('counts only the digits, not the decimal comma', () => {
    expect(digitsIn('72,2')).toBe(3)
    expect(digitsIn('143,6')).toBe(4)
  })
})

describe('fitsLabelPerBar', () => {
  it('fits a short label ("72,2", 3 digits) at 26px per bar', () => {
    expect(fitsLabelPerBar(1040, 40, 3)).toBe(true)
  })

  it('does not fit a large label ("143,6", 4 digits) at the same width and bar count', () => {
    // O caso relatado: "143,6" em cima de "131,6" colidindo na visão semanal. Mesmo
    // container, mesma contagem de barras — só o número maior já não cabe mais.
    expect(fitsLabelPerBar(1040, 40, 4)).toBe(false)
  })

  it('a wider container fits the same dense, large-label series', () => {
    expect(fitsLabelPerBar(2080, 40, 4)).toBe(true)
  })

  it('returns false with no measured width yet (avoids a flash before the first measurement)', () => {
    expect(fitsLabelPerBar(0, 12, 3)).toBe(false)
  })

  it('returns false with no bars (avoids a division by zero)', () => {
    expect(fitsLabelPerBar(1300, 0, 3)).toBe(false)
  })
})

describe('tickLabel', () => {
  it('formats a monthly tick as short month and two-digit year', () => {
    expect(tickLabel('2025-09-01T00:00:00', 'mes')).toBe('set/25')
  })

  it('formats a daily or weekly tick as "dd/mm"', () => {
    expect(tickLabel('2025-10-02T00:00:00', 'dia')).toBe('02/10')
  })
})

describe('restriction history chart', () => {
  it('shows a spinner while the series loads', () => {
    mockSeries({ isPending: true })
    renderChart()

    expect(screen.getByText('Carregando')).toBeTruthy()
  })

  it('shows the API error when the series fails to load', () => {
    mockSeries({ isError: true, error: new Error('fora do ar') })
    renderChart()

    expect(screen.getByText(/fora do ar/)).toBeTruthy()
  })

  it('shows an empty message when there is no bucket', () => {
    mockSeries({ data: { baldes: [] } })
    renderChart()

    expect(screen.getByText('Sem corte registrado nesta janela e fonte.')).toBeTruthy()
  })

  it('shows the total once the series loads', () => {
    mockSeries({
      data: { baldes: [bucket('2026-01-01', 300_000), bucket('2026-02-01', 100_000)] },
    })
    renderChart()

    expect(screen.getByText(/total 400,0 GWh/)).toBeTruthy()
  })
})
