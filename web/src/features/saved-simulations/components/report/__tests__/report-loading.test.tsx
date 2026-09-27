import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ReportLoading } from '../report-loading'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function currentStep() {
  return screen.getByRole('listitem', { current: 'step' }).textContent
}

describe('report loading', () => {
  it('starts on the first step, with the title and no percentage', () => {
    render(<ReportLoading title="Gerando seu relatório" />)

    expect(screen.getByRole('heading', { name: 'Gerando seu relatório' })).toBeTruthy()
    expect(currentStep()).toBe('Preparando seu relatório')
    expect(screen.getByRole('status').textContent).not.toMatch(/%/)
  })

  it('moves one step at a time', () => {
    render(<ReportLoading title="Gerando seu relatório" />)

    act(() => void vi.advanceTimersByTime(2500))
    expect(currentStep()).toBe('Analisando informações')

    act(() => void vi.advanceTimersByTime(2500))
    expect(currentStep()).toBe('Organizando resultados')
  })

  it('stays on the last step, without restarting, while the data does not arrive', () => {
    render(<ReportLoading title="Gerando seu relatório" />)

    for (let step = 0; step < 3; step++) act(() => void vi.advanceTimersByTime(2500))
    expect(currentStep()).toBe('Finalizando relatório…')

    act(() => void vi.advanceTimersByTime(60_000))
    expect(currentStep()).toBe('Finalizando relatório…')
  })
})
