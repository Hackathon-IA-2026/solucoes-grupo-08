import { describe, expect, it, vi } from 'vitest'
import { getReportQueryOptions, listReportsQueryOptions } from '../report'

vi.mock('@/api/client', () => ({ httpClient: { get: vi.fn(), post: vi.fn() } }))

/** O que o React Query passa ao `refetchInterval`: só o `state.data` importa aqui. */
function queryWith(state: string | undefined) {
  return { state: { data: state === undefined ? undefined : { estado: state } } } as never
}

describe('report query', () => {
  const options = getReportQueryOptions(3, 4)
  const refetchInterval = options.refetchInterval as (query: never) => number | false

  it('rereads by itself while the report is "gerando"', () => {
    expect(refetchInterval(queryWith('gerando'))).toBe(5_000)
  })

  it.each(['pronto', 'barrado', 'falhou'])('makes no further call once it is "%s"', (state) => {
    expect(refetchInterval(queryWith(state))).toBe(false)
  })

  it('makes no further call before the first answer', () => {
    expect(refetchInterval(queryWith(undefined))).toBe(false)
  })

  it('keeps reading with the tab in the background, so the screen does not stay stuck', () => {
    expect(options.refetchIntervalInBackground).toBe(true)
  })
})

describe('report list query', () => {
  const options = listReportsQueryOptions(3)
  const refetchInterval = options.refetchInterval as (query: never) => number | false
  const listWith = (...states: string[]) =>
    ({ state: { data: states.map((estado) => ({ estado })) } }) as never

  it('rereads only while some report is "gerando"', () => {
    expect(refetchInterval(listWith('pronto', 'gerando'))).toBe(5_000)
    expect(refetchInterval(listWith('pronto', 'falhou', 'barrado'))).toBe(false)
    expect(refetchInterval({ state: { data: undefined } } as never)).toBe(false)
  })
})
