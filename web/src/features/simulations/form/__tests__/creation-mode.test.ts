import { describe, expect, it, vi } from 'vitest'
import { runCreation } from '../creation-mode'

const saved = { id: 42, simulacao_id: 7 }

describe('run creation', () => {
  it('normal: saves and goes to the result, without starting agents', async () => {
    const startExploration = vi.fn()

    const outcome = await runCreation(
      { mode: 'normal' },
      { save: () => Promise.resolve(saved), startExploration },
    )

    expect(outcome).toEqual({ to: '/simulacoes/42' })
    expect(startExploration).not.toHaveBeenCalled()
  })

  it('with agents: saves, starts the exploration from the saved revision and follows it', async () => {
    const startExploration = vi.fn().mockResolvedValue({ id: 15 })

    const outcome = await runCreation(
      { mode: 'agents', agentPrompt: 'varie a potência' },
      { save: () => Promise.resolve(saved), startExploration },
    )

    expect(startExploration).toHaveBeenCalledWith(7, {
      pedido: 'varie a potência',
      revisao_partida_id: 42,
    })
    expect(outcome).toEqual({ to: '/simulacoes/7/exploracoes/15' })
  })

  it('when saving fails, reports it and starts nothing', async () => {
    const startExploration = vi.fn()

    const outcome = await runCreation(
      { mode: 'agents', agentPrompt: 'x' },
      { save: () => Promise.reject(new Error('cálculo falhou')), startExploration },
    )

    expect(outcome).toEqual({ error: { message: 'cálculo falhou' } })
    expect(startExploration).not.toHaveBeenCalled()
  })

  it('when only the agents fail, says the simulation was saved and which one', async () => {
    const outcome = await runCreation(
      { mode: 'agents', agentPrompt: 'x' },
      {
        save: () => Promise.resolve(saved),
        startExploration: () => Promise.reject(new Error('já há exploração em andamento')),
      },
    )

    expect(outcome).toEqual({
      error: {
        message:
          'A simulação foi criada, mas os agentes não começaram: já há exploração em andamento',
        savedRevisionId: 42,
      },
    })
  })
})
