import type { TaskRequest } from '@/features/agents/api/exploration'

/** Como a simulação nasce: só calculada, ou calculada e já entregue aos agentes para explorar. */
export type SimulationCreationMode = 'normal' | 'agents'

/** O que o modal de finalização devolve: o modo e, com agentes, a instrução que eles recebem. */
export type CreationChoice = { mode: 'normal' } | { mode: 'agents'; agentPrompt: string }

/** Limite da instrução no contrato (`PedidoDeTarefa.pedido`). */
export const MAX_AGENT_PROMPT = 2000

export const DEFAULT_AGENT_PROMPT =
  'Crie agentes para esta simulação com comportamentos distintos e coerentes com o contexto ' +
  'apresentado. Defina seus objetivos, características, regras de comportamento e forma de ' +
  'interação com os demais agentes. Considere diferentes perfis e perspectivas para tornar a ' +
  'simulação mais realista.'

/** Falha da criação; com `savedRevisionId`, a simulação chegou a ser salva. */
export type CreationError = { message: string; savedRevisionId?: number }

type SavedRevisionRef = { id: number; simulacao_id: number }

type CreationSteps = {
  /** Calcula e salva a simulação (`POST /simulacoes`). */
  save: () => Promise<SavedRevisionRef>
  /** Começa a exploração dos agentes (`POST /simulacoes/{id}/tarefas`). */
  startExploration: (simulationId: number, request: TaskRequest) => Promise<{ id: number }>
}

const messageOf = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback

/**
 * A criação escolhida no modal, passo a passo: salva a simulação e, com agentes, começa a
 * exploração a partir da revisão salva, com a instrução como pedido. Devolve para onde a tela vai:
 * o resultado, ou o acompanhamento da exploração. Falhando, devolve o erro; se a simulação chegou
 * a ser salva, o erro diz qual, para a tela levar a ela em vez de criar de novo.
 */
export async function runCreation(
  choice: CreationChoice,
  { save, startExploration }: CreationSteps,
): Promise<{ to: string } | { error: CreationError }> {
  let revision: SavedRevisionRef
  try {
    revision = await save()
  } catch (error) {
    return { error: { message: messageOf(error, 'Não foi possível criar a simulação.') } }
  }
  if (choice.mode === 'normal') return { to: `/simulacoes/${revision.id}` }
  try {
    const task = await startExploration(revision.simulacao_id, {
      pedido: choice.agentPrompt,
      revisao_partida_id: revision.id,
    })
    return { to: `/simulacoes/${revision.simulacao_id}/exploracoes/${task.id}` }
  } catch (error) {
    return {
      error: {
        message: `A simulação foi criada, mas os agentes não começaram: ${messageOf(error, 'erro desconhecido')}`,
        savedRevisionId: revision.id,
      },
    }
  }
}
