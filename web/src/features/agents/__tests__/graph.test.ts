import { describe, expect, it } from 'vitest'
import { buildGraph } from '../api/graph'
import { applyRecordedEvent, emptyExploration } from '../api/exploration-state'
import type { ExplorationEvent, RecordedEvent, Task } from '../api/exploration'
import { NODE_WIDTH, WAVE_GAP } from '../api/layout'

const task = { revisao_partida_id: 41, simulacao_id: 7 } as Task

function play(events: ExplorationEvent[]) {
  return events.reduce(
    (state, evento, index) =>
      applyRecordedEvent(state, {
        id: index + 1,
        tarefa_id: 1,
        instante: '',
        evento,
      } as RecordedEvent),
    emptyExploration,
  )
}

const round = (rodada: number, partida: number, ids: string[]) =>
  ({
    tipo: 'rodada_decidida',
    rodada,
    revisao_partida_id: partida,
    porque: 'x',
    variacoes: ids.map((id) => ({ alavanca: 'bateria.potencia_mw', valor: 1, variacao_id: id })),
  }) as ExplorationEvent

const ready = (id: string, revisionId: number) =>
  ({
    tipo: 'revisao_pronta',
    variacao_id: id,
    revisao_id: revisionId,
    rodada: 1,
    revisao_partida_id: 41,
  }) as ExplorationEvent

const column = NODE_WIDTH + WAVE_GAP

describe('exploration graph', () => {
  it('starts from the departure revision, with no node before there is a task', () => {
    expect(buildGraph(emptyExploration, undefined).nodes).toEqual([])
    expect(buildGraph(emptyExploration, task).nodes.map((node) => node.id)).toEqual(['start'])
  })

  it('links start to round to each variation, one stage further at each step', () => {
    const graph = buildGraph(play([round(1, 41, ['a', 'b'])]), task)

    expect(graph.edges.map((edge) => edge.id).sort()).toEqual([
      'round-1>a',
      'round-1>b',
      'start>round-1',
    ])
    const x = Object.fromEntries(graph.nodes.map((node) => [node.id, node.position.x]))
    expect(x).toEqual({ start: 0, 'round-1': column, a: 2 * column, b: 2 * column })
  })

  it('the next round reads every ready variation of the previous one, and starts from one', () => {
    const graph = buildGraph(
      play([round(1, 41, ['a', 'b', 'd']), ready('a', 42), ready('b', 43), round(2, 42, ['c'])]),
      task,
    )

    const into = graph.edges.filter((edge) => edge.target === 'round-2').map((edge) => edge.source)
    expect(into.sort()).toEqual(['a', 'b'])
    // A que não ficou pronta (d) não é lida.
    expect(into).not.toContain('d')
    expect(graph.nodes.find((node) => node.id === 'round-2')!.stage).toBe(2)
  })

  it('points the camera at the newest node still working or thinking', () => {
    const working = buildGraph(
      play([
        round(1, 41, ['a', 'b']),
        {
          tipo: 'variacao_iniciada',
          variacao_id: 'a',
          rodada: 1,
          revisao_partida_id: 41,
          alavanca: 'bateria.potencia_mw',
          valor: 1,
        },
      ]),
      task,
    )
    expect(working.activeId).toBe('a')

    const idle = buildGraph(play([round(1, 41, ['a']), ready('a', 42)]), task)
    expect(idle.activeId).toBeNull()
  })

  it('puts the report in the stage after the last round, read from its ready variations', () => {
    const graph = buildGraph(
      play([
        round(1, 41, ['a', 'b']),
        ready('a', 42),
        { tipo: 'relatorio_pedido', relatorio_id: 35 },
      ]),
      task,
    )

    const report = graph.nodes.find((node) => node.id === 'report')!
    expect(report.stage).toBe(graph.nodes.find((node) => node.id === 'round-1')!.stage + 1)
    expect(graph.edges.filter((edge) => edge.target === 'report').map((e) => e.source)).toEqual([
      'a',
    ])
  })

  it('links the report from the round itself while no variation is ready', () => {
    const graph = buildGraph(
      play([round(1, 41, ['a']), { tipo: 'relatorio_pedido', relatorio_id: 35 }]),
      task,
    )

    expect(graph.edges.some((edge) => edge.source === 'round-1' && edge.target === 'report')).toBe(
      true,
    )
  })
})
