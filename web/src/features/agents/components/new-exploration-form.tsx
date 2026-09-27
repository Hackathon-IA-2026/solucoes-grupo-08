import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { runningTaskId, useCreateTask } from '../api/exploration'
import { Textarea } from '@/components/ui/textarea'

/** Limite do pedido no contrato (`PedidoDeTarefa.pedido`). */
const MAX_REQUEST = 2000

type NewExplorationFormProps = {
  simulationId: number
  /** A revisão de onde parte. Sem ela, a API parte da revisão mais nova da simulação. */
  revisionId?: number
  onCancel: () => void
}

/**
 * Nova exploração: só o pedido. O que vai à API é o `pedido` e a `revisao_partida_id`; alavancas
 * e teto ficam no padrão dela. Criada, leva ao acompanhamento.
 */
export function NewExplorationForm({
  simulationId,
  revisionId,
  onCancel,
}: NewExplorationFormProps) {
  const [request, setRequest] = useState('')
  const navigate = useNavigate()
  const createTask = useCreateTask(simulationId)
  const trimmed = request.trim()
  const running = runningTaskId(createTask.error)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (trimmed === '') return
    createTask.mutate(
      { pedido: trimmed, revisao_partida_id: revisionId },
      { onSuccess: (task) => navigate(`/simulacoes/${simulationId}/exploracoes/${task.id}`) },
    )
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label htmlFor="pedido-exploracao" className="sr-only">
        O que explorar
      </label>
      <Textarea
        id="pedido-exploracao"
        value={request}
        onChange={(event) => setRequest(event.target.value)}
        maxLength={MAX_REQUEST}
        rows={7}
        required
        autoFocus
        placeholder="Ex.: variar a potência e a duração da bateria para ver onde o VPL deixa de piorar."
        className="resize-y border-(--sim-border) bg-(--sim-surface) text-(--sim-foreground)"
      />
      <p className="self-end text-xs tabular-nums text-(--sim-muted-foreground)">
        {request.length} / {MAX_REQUEST}
      </p>

      {createTask.isError && (
        <div role="alert" className="text-sm text-danger">
          {running != null ? (
            <>
              Já há uma exploração em andamento nesta simulação.{' '}
              <Link
                to={`/simulacoes/${simulationId}/exploracoes/${running}`}
                className="font-semibold underline"
              >
                Acompanhar a exploração {running}
              </Link>
            </>
          ) : (
            <>Não foi possível começar a exploração: {createTask.error.message}</>
          )}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <button type="button" className="sim-btn-secondary" onClick={onCancel}>
          Cancelar
        </button>
        <button
          type="submit"
          className="sim-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
          disabled={trimmed === '' || createTask.isPending}
        >
          {createTask.isPending ? 'Começando…' : 'Começar a exploração'}
        </button>
      </div>
    </form>
  )
}
