import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EVENT_TYPES } from '../api/exploration'
import { useExplorationStream } from '../api/use-exploration-stream'

class FakeEventSource {
  static instances: FakeEventSource[] = []
  static CLOSED = 2
  readyState = 1
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  listeners = new Map<string, (event: Event) => void>()
  closed = false
  url: string
  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }
  addEventListener(type: string, listener: (event: Event) => void) {
    this.listeners.set(type, listener)
  }
  removeEventListener(type: string) {
    this.listeners.delete(type)
  }
  close() {
    this.closed = true
    this.readyState = 2
  }
  emit(id: number, tipo: string, extra: object = {}) {
    const data = JSON.stringify({ id, tarefa_id: 7, instante: '', evento: { tipo, ...extra } })
    this.listeners.get(tipo)?.(new MessageEvent(tipo, { data }))
  }
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('exploration stream', () => {
  it('opens the events route of the task and listens to every event type', () => {
    renderHook(() => useExplorationStream(7))

    const source = FakeEventSource.instances[0]
    expect(source.url.endsWith('/tarefas/7/eventos')).toBe(true)
    expect([...source.listeners.keys()].sort()).toEqual([...EVENT_TYPES].sort())
  })

  it('builds the state from the events and reports the connection as live', () => {
    const { result } = renderHook(() => useExplorationStream(7))
    const source = FakeEventSource.instances[0]

    act(() => source.onopen?.())
    act(() => source.emit(1, 'decidindo_rodada', { rodada: 1 }))

    expect(result.current.connection).toBe('live')
    expect(result.current.state.rounds[1].status).toBe('thinking')
  })

  it('does not apply an event twice when the stream repeats it after a reconnection', () => {
    const { result } = renderHook(() => useExplorationStream(7))
    const source = FakeEventSource.instances[0]

    act(() => source.emit(1, 'decidindo_rodada', { rodada: 1 }))
    act(() => source.emit(1, 'decidindo_rodada', { rodada: 1 }))

    expect(result.current.state.roundNumbers).toEqual([1])
  })

  it('closes the connection on the last event, so the browser does not try to reconnect', () => {
    const { result } = renderHook(() => useExplorationStream(7))
    const source = FakeEventSource.instances[0]

    act(() => source.emit(5, 'tarefa_terminada', { estado: 'concluida', motivo: 'respondido' }))

    expect(source.closed).toBe(true)
    expect(result.current.connection).toBe('closed')
    expect(result.current.state.finished?.state).toBe('concluida')
  })

  it('says it is reconnecting on an error while the browser still retries', () => {
    const { result } = renderHook(() => useExplorationStream(7))
    const source = FakeEventSource.instances[0]

    act(() => source.onerror?.())

    expect(result.current.connection).toBe('reconnecting')
  })

  it('calls back with each event, and closes the source on unmount', () => {
    const seen: string[] = []
    const { unmount } = renderHook(() => useExplorationStream(7, (event) => seen.push(event.tipo)))
    const source = FakeEventSource.instances[0]

    act(() => source.emit(1, 'decidindo_rodada', { rodada: 1 }))
    unmount()

    expect(seen).toEqual(['decidindo_rodada'])
    expect(source.closed).toBe(true)
  })
})
