import type { ExplorationEvent, Lever, RecordedEvent, Summary } from './exploration'

export type VariationStatus = 'queued' | 'working' | 'done' | 'refused' | 'interrupted'
export type VariationStep = 'montando' | 'calculando' | 'salvando'
export type ReportState = 'gerando' | 'pronto' | 'barrado' | 'falhou'

export type Variation = {
  id: string
  round: number | null
  /** Revisão de onde a variação parte. */
  startId: number | null
  lever: Lever | null
  value: number | string | null
  status: VariationStatus
  step?: VariationStep
  revisionId?: number
  position?: number | null
  summary?: Summary | null
  reason?: string
  httpStatus?: number | null
  /** Ordem de chegada: dá a linha da variação na coluna. */
  order: number
}

export type Round = {
  number: number
  /** `ended`: a exploração terminou sem a rodada chegar a decidir variações. */
  status: 'thinking' | 'decided' | 'ended'
  why?: string
  startId?: number
  variationIds: string[]
  order: number
}

export type ExplorationState = {
  /** O último `id` aplicado: evento com id igual ou menor é repetição e não muda nada. */
  lastEventId: number
  rounds: Record<number, Round>
  roundNumbers: number[]
  variations: Record<string, Variation>
  variationIds: string[]
  report: { id: number; state: ReportState } | null
  finished: { state: 'concluida' | 'falhou'; reason: string } | null
}

export const emptyExploration: ExplorationState = {
  lastEventId: 0,
  rounds: {},
  roundNumbers: [],
  variations: {},
  variationIds: [],
  report: null,
  finished: null,
}

const TERMINAL: VariationStatus[] = ['done', 'refused', 'interrupted']

function upsertVariation(
  state: ExplorationState,
  id: string,
  base: Partial<Variation>,
): ExplorationState {
  const current = state.variations[id]
  const variation: Variation = current
    ? { ...current, ...base }
    : {
        id,
        round: null,
        startId: null,
        lever: null,
        value: null,
        status: 'queued',
        order: state.variationIds.length,
        ...base,
      }
  return {
    ...state,
    variations: { ...state.variations, [id]: variation },
    variationIds: current ? state.variationIds : [...state.variationIds, id],
  }
}

/**
 * Aplica um evento gravado ao estado. Não calcula nada do domínio: só guarda o que cada evento
 * diz. A contagem do cabeçalho vem da API (`GET /tarefas/{id}`), e não daqui.
 */
export function applyRecordedEvent(
  state: ExplorationState,
  recorded: RecordedEvent,
): ExplorationState {
  if (recorded.id <= state.lastEventId) return state
  const next = applyEvent({ ...state, lastEventId: recorded.id }, recorded.evento, recorded.id)
  return next
}

function applyEvent(
  state: ExplorationState,
  event: ExplorationEvent,
  eventId: number,
): ExplorationState {
  switch (event.tipo) {
    case 'decidindo_rodada': {
      const existing = state.rounds[event.rodada]
      if (existing) return state
      const round: Round = {
        number: event.rodada,
        status: 'thinking',
        variationIds: [],
        order: state.roundNumbers.length,
      }
      return {
        ...state,
        rounds: { ...state.rounds, [event.rodada]: round },
        roundNumbers: [...state.roundNumbers, event.rodada],
      }
    }

    case 'rodada_decidida': {
      const existing = state.rounds[event.rodada]
      // Sem `variacao_id` não há como casar a variação da fila com a que vai chegar: fica de fora.
      const planned = event.variacoes.flatMap((item) =>
        item.variacao_id ? [{ ...item, variacao_id: item.variacao_id }] : [],
      )
      const round: Round = {
        number: event.rodada,
        order: existing?.order ?? state.roundNumbers.length,
        status: 'decided',
        why: event.porque,
        startId: event.revisao_partida_id,
        variationIds: planned.map((item) => item.variacao_id),
      }
      let next: ExplorationState = {
        ...state,
        rounds: { ...state.rounds, [event.rodada]: round },
        roundNumbers: existing ? state.roundNumbers : [...state.roundNumbers, event.rodada],
      }
      for (const item of planned) {
        // Uma variação que já chegou (evento fora de ordem) não volta para a fila.
        if (next.variations[item.variacao_id]) continue
        next = upsertVariation(next, item.variacao_id, {
          round: event.rodada,
          startId: event.revisao_partida_id,
          lever: item.alavanca,
          value: item.valor,
        })
      }
      return next
    }

    case 'variacao_iniciada': {
      const current = state.variations[event.variacao_id]
      if (current && TERMINAL.includes(current.status)) return state
      return upsertVariation(state, event.variacao_id, {
        round: event.rodada ?? current?.round ?? null,
        startId: event.revisao_partida_id,
        lever: event.alavanca,
        value: event.valor,
        status: 'working',
      })
    }

    case 'variacao_passo': {
      const current = state.variations[event.variacao_id]
      if (!current || TERMINAL.includes(current.status)) return state
      return upsertVariation(state, event.variacao_id, { status: 'working', step: event.passo })
    }

    case 'revisao_pronta': {
      const current = state.variations[event.variacao_id]
      return upsertVariation(state, event.variacao_id, {
        round: event.rodada ?? current?.round ?? null,
        startId: event.revisao_partida_id ?? current?.startId ?? null,
        lever: event.alavanca ?? current?.lever ?? null,
        value: event.valor ?? current?.value ?? null,
        status: 'done',
        step: undefined,
        revisionId: event.revisao_id,
        position: event.posicao ?? null,
        summary: event.resumo ?? null,
      })
    }

    case 'variacao_recusada': {
      // O agente recusa antes de chamar a rota: sem `variacao_id`, a recusa ganha o dela.
      const id = event.variacao_id ?? `recusa-${eventId}`
      const current = state.variations[id]
      const lastRound = state.roundNumbers.at(-1)
      const round = current?.round ?? lastRound ?? null
      return upsertVariation(state, id, {
        round,
        startId:
          current?.startId ?? (round == null ? null : (state.rounds[round]?.startId ?? null)),
        lever: event.alavanca ?? current?.lever ?? null,
        value: event.valor ?? current?.value ?? null,
        status: 'refused',
        step: undefined,
        reason: event.motivo,
        httpStatus: event.status ?? null,
      })
    }

    case 'relatorio_pedido':
      return { ...state, report: { id: event.relatorio_id, state: 'gerando' } }

    case 'relatorio_pronto':
      return { ...state, report: { id: event.relatorio_id, state: event.estado } }

    case 'tarefa_terminada': {
      // O que ficou sem desfecho, na fila ou trabalhando, vira interrompido.
      const variations = Object.fromEntries(
        Object.entries(state.variations).map(([id, variation]) => [
          id,
          TERMINAL.includes(variation.status)
            ? variation
            : { ...variation, status: 'interrupted' as const, step: undefined },
        ]),
      )
      // Uma rodada que ainda pensava não vai mais decidir: para de girar.
      const rounds = Object.fromEntries(
        Object.entries(state.rounds).map(([number, round]) => [
          number,
          round.status === 'thinking' ? { ...round, status: 'ended' as const } : round,
        ]),
      )
      return {
        ...state,
        variations,
        rounds,
        finished: { state: event.estado, reason: event.motivo },
      }
    }
  }
}
