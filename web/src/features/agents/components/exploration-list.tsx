import { Link } from 'react-router'
import { taskStateLabels } from '../api/levers'
import type { Task, useTasks } from '../api/exploration'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/utils/cn'
import { formatDateTime, formatInteger } from '@/utils/format'

const stateTone: Record<Task['estado'], string> = {
  em_andamento: 'bg-(--sim-sky-soft) text-(--sim-brand)',
  concluida: 'bg-success-light text-success',
  falhou: 'bg-danger-light text-danger',
}

function TaskRow({ task, inDialog }: { task: Task; inDialog: boolean }) {
  const { contagem: counts } = task
  const url = `/simulacoes/${task.simulacao_id}/exploracoes/${task.id}`
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 py-4">
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="sim-display text-sm font-semibold text-(--sim-brand-ink)">
            Exploração {task.id}
          </span>
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-[0.68rem] font-bold',
              stateTone[task.estado],
            )}
          >
            {taskStateLabels[task.estado]}
          </span>
        </div>
        <p className="line-clamp-2 text-sm text-(--sim-foreground)" title={task.pedido}>
          {task.pedido}
        </p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs tabular-nums text-(--sim-muted-foreground)">
          <span>{formatDateTime(task.criada_em)}</span>
          <span aria-hidden="true">·</span>
          <span>Partiu da revisão {task.revisao_partida_id}</span>
          <span aria-hidden="true">·</span>
          <span>
            {formatInteger(counts.prontas)} de {formatInteger(task.teto)} revisões prontas
          </span>
          {counts.recusadas > 0 && (
            <>
              <span aria-hidden="true">·</span>
              <span>{formatInteger(counts.recusadas)} recusadas</span>
            </>
          )}
        </div>
        {(task.erro ?? task.motivo) && (
          <p className={cn('text-xs', task.erro ? 'text-danger' : 'text-(--sim-muted-foreground)')}>
            {task.erro ?? task.motivo}
          </p>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {!inDialog && task.relatorio_id != null && (
          <Link
            to={`/simulacoes/${task.simulacao_id}/relatorios/${task.relatorio_id}`}
            className="sim-btn-secondary"
          >
            Relatório
          </Link>
        )}
        <Link
          to={url}
          className={task.estado === 'em_andamento' ? 'sim-btn-primary' : 'sim-btn-secondary'}
          aria-label={`${inDialog ? 'Abrir' : 'Ver processamento da'} exploração ${task.id}`}
        >
          {task.estado === 'em_andamento' ? 'Acompanhar' : inDialog ? 'Abrir' : 'Ver processamento'}
        </Link>
      </div>
    </li>
  )
}

function TasksSkeleton() {
  return (
    <ul className="divide-y divide-(--sim-border)" aria-label="Carregando explorações">
      {[0, 1, 2].map((row) => (
        <li key={row} className="flex items-center justify-between gap-4 px-5 py-4">
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3.5 w-72" />
          </div>
          <Skeleton className="h-9 w-28" />
        </li>
      ))}
    </ul>
  )
}

/**
 * O miolo da lista de explorações de uma simulação: contagem, carregamento, erro, vazio e as
 * linhas. Serve à página e ao modal; quem chama põe o cabeçalho e o botão de nova exploração.
 */
export function ExplorationList({
  tasks,
  onNew,
  inDialog = false,
}: {
  tasks: ReturnType<typeof useTasks>
  onNew: () => void
  /** No modal a linha é enxuta: sem o botão de relatório, e "Abrir" no lugar de "Ver processamento". */
  inDialog?: boolean
}) {
  const count = tasks.data?.length
  return (
    <section aria-label="Lista de explorações" className="sim-card">
      {count !== undefined && count > 0 && (
        <div className="sim-card-head border-b border-(--sim-border) px-5 py-3">
          <p className="text-xs font-semibold text-(--sim-brand-ink)">
            {count} {count === 1 ? 'exploração' : 'explorações'}
          </p>
        </div>
      )}
      {tasks.isPending ? (
        <TasksSkeleton />
      ) : tasks.isError ? (
        <div
          role="alert"
          className="flex flex-col gap-3 px-5 py-4 text-xs leading-5 text-(--sim-muted-foreground) sm:flex-row sm:items-center"
        >
          <span>Erro ao carregar as explorações: {tasks.error.message}</span>
          <button type="button" className="sim-btn-secondary" onClick={() => tasks.refetch()}>
            Tentar novamente
          </button>
        </div>
      ) : tasks.data.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
          <p className="text-sm font-semibold text-(--sim-brand-ink)">
            Nenhuma exploração nesta simulação
          </p>
          <button type="button" className="sim-btn-secondary" onClick={onNew}>
            Começar a primeira
          </button>
        </div>
      ) : (
        <ul className="divide-y divide-(--sim-border)">
          {tasks.data.map((task) => (
            <TaskRow key={task.id} task={task} inDialog={inDialog} />
          ))}
        </ul>
      )}
    </section>
  )
}
