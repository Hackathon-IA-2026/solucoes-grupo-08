export const NODE_WIDTH = 300
/** Altura de referência de um cartão, para enquadrar a câmera antes de o nó ser medido. */
export const NODE_HEIGHT = 150
/** Vão entre um cartão de comando (partida, rodada, relatório) e o bloco de agentes seguinte. */
export const WAVE_GAP = 96
/** Vão entre duas colunas de agentes do mesmo bloco. */
export const AGENT_GAP = 46
/** Espaço vertical mínimo entre dois cartões da mesma coluna. */
export const ROW_GAP = 28

/** Agentes por coluna a partir dos quais o bloco ganha outra coluna. */
const ROWS_PER_COLUMN = 4
/** Colunas de agentes de um bloco: mais que isso o desenho cresce para baixo. */
const MAX_AGENT_COLUMNS = 3

export type Placeable = {
  id: string
  /**
   * `hub` é um cartão de comando (partida, rodada, relatório): um por etapa, no eixo do desenho.
   * `agent` é uma variação: vai para o bloco de agentes da etapa.
   */
  kind: 'hub' | 'agent'
  /** A etapa, da esquerda para a direita: comando primeiro, agentes dele logo à direita. */
  stage: number
  order: number
  height: number
}

/** Colunas de um bloco de `count` agentes: 8 ficam em duas, 10 em três, 4 ou menos em uma. */
export function agentColumns(count: number) {
  return Math.min(MAX_AGENT_COLUMNS, Math.max(1, Math.ceil(count / ROWS_PER_COLUMN)))
}

type Laid = { id: string; x: number; y: number }

/**
 * O bloco de agentes de uma etapa, com o canto superior esquerdo em (0, 0): fileiras de `columns`
 * agentes na ordem em que chegaram, e cada coluna descida uma fração da fileira em relação à
 * anterior. Esse degrau é o que deixa a coluna de trás aparecer entre os cartões da da frente, e
 * as ligações do comando chegarem a ela pelos vãos.
 */
function agentBlock(agents: Placeable[]) {
  const columns = agentColumns(agents.length)
  const pitch = Math.max(...agents.map((agent) => agent.height)) + ROW_GAP
  const laid: Laid[] = agents.map((agent, index) => ({
    id: agent.id,
    x: (index % columns) * (NODE_WIDTH + AGENT_GAP),
    y: Math.floor(index / columns) * pitch + ((index % columns) * pitch) / columns,
  }))
  const height = Math.max(...laid.map((cell, i) => cell.y + agents[i].height))
  return { laid, width: columns * NODE_WIDTH + (columns - 1) * AGENT_GAP, height }
}

/**
 * Posição de cada nó no desenho por ondas: da esquerda para a direita, uma etapa depois da outra.
 * Cada etapa é um cartão de comando e, à direita dele, o bloco de agentes que ele disparou, em
 * grade de até três colunas. Todas as etapas se centram no mesmo eixo horizontal, então o comando
 * fica na altura do meio do bloco e o desenho só cresce para baixo (e para cima, junto) quando o
 * maior bloco pede.
 */
export function layoutWaves(items: Placeable[]) {
  const byStage = new Map<number, { hub?: Placeable; agents: Placeable[] }>()
  for (const item of [...items].sort((a, b) => a.order - b.order)) {
    const stage = byStage.get(item.stage) ?? { agents: [] }
    if (item.kind === 'hub') stage.hub = item
    else stage.agents.push(item)
    byStage.set(item.stage, stage)
  }
  const stages = [...byStage.entries()].sort(([a], [b]) => a - b).map(([, stage]) => stage)

  const blocks = stages.map((stage) => (stage.agents.length > 0 ? agentBlock(stage.agents) : null))
  const tallest = Math.max(
    0,
    ...stages.map((s) => s.hub?.height ?? 0),
    ...blocks.map((b) => b?.height ?? 0),
  )
  const axis = tallest / 2

  const positions = new Map<string, { x: number; y: number }>()
  let x = 0
  stages.forEach((stage, index) => {
    if (stage.hub) {
      positions.set(stage.hub.id, { x, y: axis - stage.hub.height / 2 })
      x += NODE_WIDTH + WAVE_GAP
    }
    const block = blocks[index]
    if (block) {
      const top = axis - block.height / 2
      for (const cell of block.laid) positions.set(cell.id, { x: x + cell.x, y: top + cell.y })
      x += block.width + WAVE_GAP
    }
  })
  return positions
}
