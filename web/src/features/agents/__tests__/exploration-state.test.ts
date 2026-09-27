import { describe, expect, it } from 'vitest'
import type { ExplorationEvent, RecordedEvent } from '../api/exploration'
import { applyRecordedEvent, emptyExploration } from '../api/exploration-state'

function play(events: ExplorationEvent[]) {
  return events.reduce(
    (state, evento, index) =>
      applyRecordedEvent(state, {
        id: index + 1,
        tarefa_id: 1,
        instante: '2026-09-23T20:00:00Z',
        evento,
      } as RecordedEvent),
    emptyExploration,
  )
}

const decided = (variacoes: { id: string; valor: number }[], rodada = 1, partida = 41) =>
  ({
    tipo: 'rodada_decidida',
    rodada,
    revisao_partida_id: partida,
    porque: 'A curva achata.',
    variacoes: variacoes.map((item) => ({
      alavanca: 'bateria.potencia_mw',
      valor: item.valor,
      variacao_id: item.id,
    })),
  }) as ExplorationEvent

const started = (id: string) =>
  ({
    tipo: 'variacao_iniciada',
    variacao_id: id,
    rodada: 1,
    revisao_partida_id: 41,
    alavanca: 'bateria.potencia_mw',
    valor: 100,
  }) as ExplorationEvent

const ready = (id: string, revisionId: number) =>
  ({
    tipo: 'revisao_pronta',
    variacao_id: id,
    revisao_id: revisionId,
    posicao: 2,
    revisao_partida_id: 41,
    rodada: 1,
    resumo: {
      energia_recuperada_mwh: 2000,
      fracao_recuperada: 0.18,
      vpl_reais: -3e7,
      tir_aa: null,
      payback_simples_anos: null,
      custo_por_mwh_reais: 310,
      avisos: 2,
    },
  }) as ExplorationEvent

describe('exploration state', () => {
  it('shows the round as thinking, then decided with its reason and a queue of variations', () => {
    const thinking = play([{ tipo: 'decidindo_rodada', rodada: 1 }])
    expect(thinking.rounds[1].status).toBe('thinking')

    const state = play([
      { tipo: 'decidindo_rodada', rodada: 1 },
      decided([
        { id: 'r1-v1', valor: 100 },
        { id: 'r1-v2', valor: 200 },
      ]),
    ])
    expect(state.rounds[1]).toMatchObject({
      status: 'decided',
      why: 'A curva achata.',
      startId: 41,
    })
    expect(state.variationIds).toEqual(['r1-v1', 'r1-v2'])
    expect(state.variations['r1-v1'].status).toBe('queued')
  })

  it('walks a variation from queue to working, through its steps, to a ready revision', () => {
    const state = play([
      decided([{ id: 'r1-v1', valor: 100 }]),
      started('r1-v1'),
      { tipo: 'variacao_passo', variacao_id: 'r1-v1', passo: 'calculando' },
      ready('r1-v1', 42),
    ])

    expect(state.variations['r1-v1']).toMatchObject({
      status: 'done',
      revisionId: 42,
      position: 2,
      step: undefined,
    })
    expect(state.variations['r1-v1'].summary?.fracao_recuperada).toBe(0.18)
  })

  it('keeps parallel variations apart, grouped by variation id', () => {
    const state = play([
      decided([
        { id: 'a', valor: 1 },
        { id: 'b', valor: 2 },
      ]),
      started('a'),
      started('b'),
      { tipo: 'variacao_passo', variacao_id: 'b', passo: 'salvando' },
      { tipo: 'variacao_passo', variacao_id: 'a', passo: 'montando' },
    ])

    expect(state.variations.a.step).toBe('montando')
    expect(state.variations.b.step).toBe('salvando')
  })

  it('ignores a repeated or older event id, as after a reconnection', () => {
    const first = play([decided([{ id: 'a', valor: 1 }]), started('a')])
    const again = applyRecordedEvent(first, {
      id: 2,
      tarefa_id: 1,
      instante: '2026-09-23T20:00:00Z',
      evento: ready('a', 9),
    } as RecordedEvent)

    expect(again).toBe(first)
    expect(again.variations.a.status).toBe('working')
  })

  it('records a refusal from the route, and one from the agent that has no variation id', () => {
    const state = play([
      decided([{ id: 'a', valor: 200 }]),
      {
        tipo: 'variacao_recusada',
        variacao_id: 'a',
        alavanca: 'bateria.potencia_mw',
        valor: 200,
        status: 422,
        motivo: 'acima do teto',
      },
      {
        tipo: 'variacao_recusada',
        variacao_id: null,
        alavanca: 'bateria.potencia_mw',
        valor: 900,
        motivo: 'fora da faixa',
      },
    ])

    expect(state.variations.a).toMatchObject({
      status: 'refused',
      reason: 'acima do teto',
      httpStatus: 422,
    })
    const orphan = Object.values(state.variations).find((variation) => variation.id !== 'a')!
    expect(orphan).toMatchObject({
      status: 'refused',
      round: 1,
      startId: 41,
      reason: 'fora da faixa',
    })
  })

  it('a finished exploration turns whatever had no outcome into interrupted', () => {
    const state = play([
      decided([
        { id: 'a', valor: 1 },
        { id: 'b', valor: 2 },
        { id: 'c', valor: 3 },
      ]),
      started('a'),
      started('b'),
      ready('b', 50),
      { tipo: 'tarefa_terminada', estado: 'falhou', motivo: 'sem evento por 20 minutos' },
    ])

    expect(state.variations.a.status).toBe('interrupted')
    expect(state.variations.b.status).toBe('done')
    expect(state.variations.c.status).toBe('interrupted')
    expect(state.finished).toEqual({ state: 'falhou', reason: 'sem evento por 20 minutos' })
  })

  it('tracks the report from requested to its final state', () => {
    const asked = play([{ tipo: 'relatorio_pedido', relatorio_id: 35 }])
    expect(asked.report).toEqual({ id: 35, state: 'gerando' })

    const done = play([
      { tipo: 'relatorio_pedido', relatorio_id: 35 },
      { tipo: 'relatorio_pronto', relatorio_id: 35, estado: 'barrado' },
    ])
    expect(done.report).toEqual({ id: 35, state: 'barrado' })
  })

  it('skips a planned variation with no id, since nothing could match it later', () => {
    const state = play([
      {
        tipo: 'rodada_decidida',
        rodada: 1,
        revisao_partida_id: 41,
        porque: 'x',
        variacoes: [{ alavanca: 'bateria.potencia_mw', valor: 100, variacao_id: null }],
      } as ExplorationEvent,
    ])

    expect(state.variationIds).toEqual([])
  })

  it('a round still thinking when the exploration ends stops spinning, as ended', () => {
    const state = play([
      { tipo: 'decidindo_rodada', rodada: 3 },
      { tipo: 'tarefa_terminada', estado: 'concluida', motivo: 'respondido' },
    ])

    expect(state.rounds[3].status).toBe('ended')
  })
})
