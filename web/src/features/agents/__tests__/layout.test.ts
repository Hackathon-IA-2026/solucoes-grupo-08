import { describe, expect, it } from 'vitest'
import {
  agentColumns,
  AGENT_GAP,
  layoutWaves,
  NODE_WIDTH,
  ROW_GAP,
  WAVE_GAP,
  type Placeable,
} from '../api/layout'

let order = 0
const hub = (id: string, stage: number, height = 150): Placeable => ({
  id,
  kind: 'hub',
  stage,
  order: order++,
  height,
})
const agents = (prefix: string, stage: number, count: number, height = 170) =>
  Array.from({ length: count }, (_, i) => ({
    id: `${prefix}${i}`,
    kind: 'agent' as const,
    stage,
    order: order++,
    height,
  }))

/** O que o layout promete: nenhum cartão encosta em outro, e cada comando fica no eixo do desenho. */
function expectReadable(items: Placeable[]) {
  const positions = layoutWaves(items)
  const box = (id: string) => {
    const p = positions.get(id)
    const item = items.find((i) => i.id === id)
    if (!p || !item) throw new Error(`sem posição: ${id}`)
    return {
      ...p,
      right: p.x + NODE_WIDTH,
      bottom: p.y + item.height,
      center: p.y + item.height / 2,
    }
  }
  expect(positions.size).toBe(items.length)
  for (const a of items) {
    for (const b of items) {
      if (a.id >= b.id) continue
      const pa = box(a.id)
      const pb = box(b.id)
      const apartX = pa.right <= pb.x || pb.right <= pa.x
      const apartY = pa.bottom + ROW_GAP <= pb.y || pb.bottom + ROW_GAP <= pa.y
      expect(apartX || apartY, `${a.id} encosta em ${b.id}`).toBe(true)
    }
  }
  const height = Math.max(...items.map((i) => box(i.id).bottom))
  return { box, height }
}

describe('waves layout', () => {
  it('puts the command first and its agents to the right, stage after stage', () => {
    const { box } = expectReadable([
      hub('start', 0),
      hub('r1', 1),
      ...agents('a', 1, 2),
      hub('r2', 2),
      ...agents('b', 2, 2),
    ])

    expect(box('start').x).toBe(0)
    expect(box('r1').x).toBe(NODE_WIDTH + WAVE_GAP)
    expect(box('a0').x).toBe(2 * (NODE_WIDTH + WAVE_GAP))
    expect(box('r2').x).toBeGreaterThan(box('a0').x + NODE_WIDTH)
    expect(box('b0').x).toBe(box('r2').x + NODE_WIDTH + WAVE_GAP)
  })

  it('picks the number of columns from the number of agents', () => {
    expect(agentColumns(1)).toBe(1)
    expect(agentColumns(4)).toBe(1)
    expect(agentColumns(8)).toBe(2)
    expect(agentColumns(10)).toBe(3)
    expect(agentColumns(40)).toBe(3)
  })

  it('lays eight agents in two columns and ten in three, filled by row', () => {
    const two = expectReadable([hub('r1', 1), ...agents('a', 1, 8)])
    expect(new Set(Array.from({ length: 8 }, (_, i) => two.box(`a${i}`).x)).size).toBe(2)
    expect(two.box('a1').x - two.box('a0').x).toBe(NODE_WIDTH + AGENT_GAP)

    const three = expectReadable([hub('r1', 1), ...agents('a', 1, 10)])
    expect(new Set(Array.from({ length: 10 }, (_, i) => three.box(`a${i}`).x)).size).toBe(3)
    // Uma coluna só seriam 10 cartões empilhados.
    expect(three.height).toBeLessThan(10 * 170)
  })

  it('steps each column down from the previous one, so the columns interleave', () => {
    const { box } = expectReadable([hub('r1', 1), ...agents('a', 1, 8)])

    expect(box('a1').y).toBeGreaterThan(box('a0').y)
    expect(box('a1').y).toBeLessThan(box('a2').y)
  })

  it('centers every stage on the same axis, the command at the middle of its agents', () => {
    const { box } = expectReadable([
      hub('r1', 1),
      ...agents('a', 1, 12),
      hub('r2', 2),
      ...agents('b', 2, 2),
    ])

    const top = Math.min(...Array.from({ length: 12 }, (_, i) => box(`a${i}`).y))
    const bottom = Math.max(...Array.from({ length: 12 }, (_, i) => box(`a${i}`).bottom))
    expect(box('r1').center).toBeCloseTo((top + bottom) / 2)
    expect(box('r2').center).toBeCloseTo(box('r1').center)
  })

  it('grows only as tall as the biggest block asks', () => {
    const small = expectReadable([hub('r1', 1), ...agents('a', 1, 4)]).height
    const bigger = expectReadable([
      hub('r1', 1),
      ...agents('a', 1, 4),
      hub('r2', 2),
      ...agents('b', 2, 30),
    ])

    expect(bigger.height).toBeGreaterThan(small)
    // Quatro rodadas de dez não somam alturas: ficam lado a lado.
    const rounds = Array.from({ length: 4 }, (_, r) => [
      hub(`h${r}`, r + 1),
      ...agents(`v${r}-`, r + 1, 10),
    ]).flat()
    const one = expectReadable([hub('h', 1), ...agents('v', 1, 10)]).height
    expect(expectReadable(rounds).height).toBeLessThanOrEqual(one + 0.001)
  })

  it('handles a stage with a command and no agents yet, and stages with only agents', () => {
    expectReadable([hub('start', 0), hub('r1', 1)])
    expectReadable([...agents('loose', 0, 3), hub('r1', 1), ...agents('a', 1, 2)])
  })
})
