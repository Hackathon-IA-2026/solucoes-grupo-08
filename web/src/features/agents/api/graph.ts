import type { ExplorationState, Round, Variation } from './exploration-state'
import type { Task } from './exploration'
import { layoutWaves, NODE_HEIGHT } from './layout'

export type GraphNode =
  | { id: string; kind: 'start'; stage: number; order: number; revisionId: number }
  | { id: string; kind: 'round'; stage: number; order: number; round: Round }
  | { id: string; kind: 'variation'; stage: number; order: number; variation: Variation }
  | {
      id: string
      kind: 'report'
      stage: number
      order: number
      report: NonNullable<ExplorationState['report']>
    }

export type EdgeStatus = 'queued' | 'working' | 'done' | 'refused' | 'idle'

export type GraphEdge = { id: string; source: string; target: string; status: EdgeStatus }

export type Graph = {
  nodes: (GraphNode & { position: { x: number; y: number } })[]
  edges: GraphEdge[]
  /** O nó em que a atenção deve estar agora: o que está pensando ou trabalhando, o mais novo. */
  activeId: string | null
}

const roundId = (number: number) => `round-${number}`

/** Altura de um nó ainda não medido na tela; a medida real a substitui assim que existe. */
const estimatedHeight: Record<GraphNode['kind'], number> = {
  start: 80,
  round: NODE_HEIGHT,
  variation: 170,
  report: 90,
}

/** Altura medida de cada nó na tela, pelo id. */
export type NodeHeights = Readonly<Record<string, number>>

/**
 * Monta o grafo da exploração, por ondas: a partida, e a cada rodada o cartão dela com as
 * variações que disparou logo à direita. A rodada seguinte lê o resultado das variações prontas
 * da anterior (e parte de uma delas, ou da partida), e o relatório lê as da última rodada: por
 * isso as ligações entram nesses cartões vindas de cada variação pronta, e não só da que serviu
 * de partida. Uma pura transformação do que os eventos disseram.
 */
export function buildGraph(
  state: ExplorationState,
  task: Task | undefined,
  heights: NodeHeights = {},
): Graph {
  const startNodeId = 'start'
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []
  const edgeIds = new Set<string>()
  const link = (source: string, target: string, status: EdgeStatus) => {
    const id = `${source}>${target}`
    if (edgeIds.has(id)) return
    edgeIds.add(id)
    edges.push({ id, source, target, status })
  }

  if (task) {
    nodes.push({
      id: startNodeId,
      kind: 'start',
      stage: 0,
      order: 0,
      revisionId: task.revisao_partida_id,
    })
  }

  // A revisão de partida de uma rodada é o nó inicial ou a variação que a salvou.
  const nodeOfRevision = (revisionId: number | null | undefined) => {
    if (revisionId == null || revisionId === task?.revisao_partida_id) return startNodeId
    const saved = Object.values(state.variations).find(
      (variation) => variation.revisionId === revisionId,
    )
    return saved ? saved.id : startNodeId
  }

  const edgeStatus = (variation: Variation): EdgeStatus =>
    variation.status === 'working'
      ? 'working'
      : variation.status === 'done'
        ? 'done'
        : variation.status === 'refused'
          ? 'refused'
          : variation.status === 'queued'
            ? 'queued'
            : 'idle'

  let order = 1
  const addVariation = (variation: Variation, stage: number, parent: string | undefined) => {
    nodes.push({ id: variation.id, kind: 'variation', stage, order: order++, variation })
    if (parent) link(parent, variation.id, edgeStatus(variation))
  }
  const readyOf = (numbers: number[]) =>
    state.variationIds.filter((id) => {
      const variation = state.variations[id]
      return (
        variation.status === 'done' && variation.round != null && numbers.includes(variation.round)
      )
    })

  // Uma etapa por rodada, na ordem dos números; a partida é a etapa 0.
  const numbers = [...state.roundNumbers].sort((a, b) => a - b)
  numbers.forEach((number, index) => {
    const stage = index + 1
    const round = state.rounds[number]
    const seed = round.startId == null ? undefined : nodeOfRevision(round.startId)
    nodes.push({ id: roundId(number), kind: 'round', stage, order: order++, round })
    // A rodada lê as variações prontas da anterior, e parte da que a API disse (ou da partida).
    const reads = index > 0 ? readyOf([numbers[index - 1]]) : []
    const status: EdgeStatus = round.status === 'thinking' ? 'working' : 'done'
    for (const source of new Set([...(seed ? [seed] : []), ...reads])) {
      link(source, roundId(number), status)
    }
    for (const id of state.variationIds) {
      if (state.variations[id].round === number) {
        addVariation(state.variations[id], stage, roundId(number))
      }
    }
  })
  // Variação sem rodada conhecida (uma recusa do agente antes de qualquer rodada): sem ligação,
  // no bloco de agentes da partida.
  for (const id of state.variationIds) {
    const variation = state.variations[id]
    if (variation.round == null || !state.rounds[variation.round])
      addVariation(variation, 0, undefined)
  }

  if (state.report) {
    const lastRound = numbers.at(-1)
    nodes.push({
      id: 'report',
      kind: 'report',
      stage: numbers.length + 1,
      order: order++,
      report: state.report,
    })
    const status: EdgeStatus = state.report.state === 'gerando' ? 'working' : 'done'
    const reads = lastRound != null ? readyOf([lastRound]) : []
    // Sem variação pronta para ler, o relatório sai da própria rodada.
    for (const source of reads.length > 0 ? reads : lastRound != null ? [roundId(lastRound)] : []) {
      link(source, 'report', status)
    }
  }

  const positions = layoutWaves(
    nodes.map((node) => ({
      id: node.id,
      kind: node.kind === 'variation' ? ('agent' as const) : ('hub' as const),
      stage: node.stage,
      order: node.order,
      height: heights[node.id] ?? estimatedHeight[node.kind],
    })),
  )
  const active = [...nodes]
    .reverse()
    .find(
      (node) =>
        (node.kind === 'round' && node.round.status === 'thinking') ||
        (node.kind === 'variation' && node.variation.status === 'working') ||
        (node.kind === 'report' && node.report.state === 'gerando'),
    )

  return {
    nodes: nodes.map((node) => ({ ...node, position: positions.get(node.id) ?? { x: 0, y: 0 } })),
    edges,
    activeId: active?.id ?? null,
  }
}
