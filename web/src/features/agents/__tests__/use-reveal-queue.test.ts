import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { REVEAL_MIN_MS, REVEAL_MS, useRevealQueue } from '../api/use-reveal-queue'

const nodes = (count: number) => Array.from({ length: count }, (_, i) => ({ id: `n${i}` }))

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

const ids = (revealed: ReadonlySet<string>) => [...revealed]

describe('reveal queue', () => {
  it('shows the first node at once and the others one at a time, in order', () => {
    const { result } = renderHook(() => useRevealQueue(nodes(3)))

    act(() => vi.advanceTimersByTime(0))
    expect(ids(result.current.revealed)).toEqual(['n0'])

    act(() => vi.advanceTimersByTime(REVEAL_MS - 1))
    expect(ids(result.current.revealed)).toEqual(['n0'])
    act(() => vi.advanceTimersByTime(1))
    expect(ids(result.current.revealed)).toEqual(['n0', 'n1'])

    act(() => vi.advanceTimersByTime(REVEAL_MS))
    expect(ids(result.current.revealed)).toEqual(['n0', 'n1', 'n2'])
    expect(result.current.waiting).toBe(0)
  })

  it('speeds up when many are waiting, so a finished exploration does not take a minute', () => {
    const { result } = renderHook(() => useRevealQueue(nodes(80)))

    act(() => vi.advanceTimersByTime(0))
    // Com 79 na fila o passo cai ao mínimo, e não fica nos 450 ms do caso calmo.
    act(() => vi.advanceTimersByTime(REVEAL_MIN_MS))
    expect(result.current.revealed.size).toBe(2)
    act(() => vi.advanceTimersByTime(REVEAL_MIN_MS))
    expect(result.current.revealed.size).toBe(3)

    // Tudo no ar em bem menos que os 80 x 450 ms = 36 s do passo calmo.
    for (let i = 0; i < 120; i += 1) act(() => vi.advanceTimersByTime(REVEAL_MS))
    expect(result.current.waiting).toBe(0)
  })

  it('stays calm with only a few waiting', () => {
    const { result } = renderHook(() => useRevealQueue(nodes(3)))

    act(() => vi.advanceTimersByTime(0))
    act(() => vi.advanceTimersByTime(REVEAL_MS - 1))
    expect(result.current.revealed.size).toBe(1)
  })

  it('queues nodes that arrive later behind the ones already shown', () => {
    const { result, rerender } = renderHook(({ list }) => useRevealQueue(list), {
      initialProps: { list: nodes(2) },
    })
    act(() => vi.advanceTimersByTime(0))
    act(() => vi.advanceTimersByTime(REVEAL_MS))
    expect(result.current.waiting).toBe(0)

    rerender({ list: nodes(4) })
    expect(result.current.waiting).toBe(2)
    act(() => vi.advanceTimersByTime(REVEAL_MS))
    expect(ids(result.current.revealed)).toEqual(['n0', 'n1', 'n2'])
    act(() => vi.advanceTimersByTime(REVEAL_MS))
    expect(ids(result.current.revealed)).toEqual(['n0', 'n1', 'n2', 'n3'])
  })

  it('does not restart the wait when the same nodes come back as new objects', () => {
    const { result, rerender } = renderHook(({ list }) => useRevealQueue(list), {
      initialProps: { list: nodes(3) },
    })
    act(() => vi.advanceTimersByTime(0))
    act(() => vi.advanceTimersByTime(REVEAL_MS - 50))
    rerender({ list: nodes(3) })
    act(() => vi.advanceTimersByTime(50))

    expect(ids(result.current.revealed)).toEqual(['n0', 'n1'])
  })
})
