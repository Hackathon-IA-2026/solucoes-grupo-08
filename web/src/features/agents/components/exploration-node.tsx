import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { Check, CircleAlert, FileText, LoaderCircle, Route } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { GraphNode } from '../api/graph'
import { leverLabel, leverValue } from '../api/levers'
import { NODE_WIDTH } from '../api/layout'
import type { ReportState, Variation, VariationStep } from '../api/exploration-state'
import { cn } from '@/utils/cn'
import { formatFractionAsPercent, formatNumber } from '@/utils/format'

export type ExplorationNodeData = { node: GraphNode; simulationId: number }
export type ExplorationFlowNode = Node<ExplorationNodeData, 'exploration'>

const stepLabels: Record<VariationStep, string> = {
  montando: 'Montando a configuração',
  calculando: 'Calculando no motor',
  salvando: 'Salvando a revisão',
}

const reportLabels: Record<ReportState, string> = {
  gerando: 'Gerando',
  pronto: 'Pronto',
  barrado: 'Barrado',
  falhou: 'Falhou',
}

type Tone = 'idle' | 'working' | 'done' | 'failed'

const toneBorder: Record<Tone, string> = {
  idle: 'border-(--sim-border)',
  working: 'border-(--sim-brand)',
  done: 'border-success',
  failed: 'border-danger',
}

function Shell({
  tone,
  dashed,
  children,
  label,
}: {
  tone: Tone
  dashed?: boolean
  children: ReactNode
  label: string
}) {
  return (
    <article
      style={{ width: NODE_WIDTH }}
      aria-label={label}
      className={cn(
        'rounded-lg border-[1.5px] bg-(--sim-surface) p-3 text-(--sim-foreground) shadow-[0_6px_18px_-12px_rgba(15,23,42,0.35)] motion-safe:animate-[agent-in_0.35s_ease-out]',
        toneBorder[tone],
        dashed && 'border-dashed',
      )}
    >
      <Handle type="target" position={Position.Left} className="opacity-0!" isConnectable={false} />
      {children}
      <Handle
        type="source"
        position={Position.Right}
        className="opacity-0!"
        isConnectable={false}
      />
    </article>
  )
}

function Head({
  icon,
  title,
  subtitle,
  spinning,
}: {
  icon: ReactNode
  title: string
  subtitle?: string
  spinning?: boolean
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className="relative grid size-8 shrink-0 place-items-center rounded-lg bg-(--sim-sky-soft) text-(--sim-brand)"
        aria-hidden="true"
      >
        {icon}
        {spinning && (
          <span className="absolute -inset-1 rounded-xl border-2 border-(--sim-brand) border-t-transparent motion-safe:animate-spin" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="sim-display truncate text-[0.8125rem] font-semibold text-(--sim-brand-ink)">
          {title}
        </p>
        {subtitle && (
          <p className="truncate text-[0.7rem] text-(--sim-muted-foreground)">{subtitle}</p>
        )}
      </div>
    </div>
  )
}

function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        'w-fit rounded-full px-2 py-0.5 text-[0.68rem] font-bold',
        tone === 'idle' && 'bg-(--sim-muted) text-(--sim-muted-foreground)',
        tone === 'working' && 'bg-(--sim-sky-soft) text-(--sim-brand)',
        tone === 'done' && 'bg-success-light text-success',
        tone === 'failed' && 'bg-danger-light text-danger',
      )}
    >
      {children}
    </span>
  )
}

function VariationBody({ variation }: { variation: Variation }) {
  const { status, summary } = variation
  const tone: Tone =
    status === 'working'
      ? 'working'
      : status === 'done'
        ? 'done'
        : status === 'refused'
          ? 'failed'
          : 'idle'

  return (
    <>
      <Head
        icon={
          status === 'done' ? (
            <Check className="size-4" />
          ) : status === 'refused' ? (
            <CircleAlert className="size-4" />
          ) : (
            <LoaderCircle className="size-4" />
          )
        }
        title={`${leverLabel(variation.lever)} · ${leverValue(variation.lever, variation.value)}`}
        subtitle={variation.round == null ? undefined : `Rodada ${variation.round}`}
        spinning={status === 'working'}
      />

      {status === 'working' && (
        <p className="mt-2.5 flex items-center gap-1 text-xs">
          <span className="truncate">
            {variation.step ? stepLabels[variation.step] : 'Começando'}
          </span>
          <span
            className="inline-block h-3 w-1.5 shrink-0 bg-(--sim-muted-foreground) motion-safe:animate-pulse"
            aria-hidden="true"
          />
        </p>
      )}

      {status === 'done' && summary && (
        <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1 text-xs tabular-nums">
          <div>
            <dt className="text-(--sim-muted-foreground)">Fração</dt>
            <dd className="font-bold text-(--sim-brand-ink)">
              {formatFractionAsPercent(summary.fracao_recuperada)} %
            </dd>
          </div>
          <div>
            <dt className="text-(--sim-muted-foreground)">VPL</dt>
            <dd className="font-bold text-(--sim-brand-ink)">
              R$ {formatNumber(summary.vpl_reais)}
            </dd>
          </div>
          <div>
            <dt className="text-(--sim-muted-foreground)">Payback</dt>
            <dd className="font-bold text-(--sim-brand-ink)">
              {summary.payback_simples_anos == null
                ? '—'
                : `${formatNumber(summary.payback_simples_anos, 1)} anos`}
            </dd>
          </div>
          <div>
            <dt className="text-(--sim-muted-foreground)">Avisos</dt>
            <dd className="font-bold text-(--sim-brand-ink)">{formatNumber(summary.avisos)}</dd>
          </div>
        </dl>
      )}

      {status === 'refused' && (
        <p className="mt-2.5 text-xs leading-5 text-danger">
          {variation.reason}
          {variation.httpStatus ? (
            <span className="tabular-nums"> ({variation.httpStatus})</span>
          ) : null}
        </p>
      )}

      <div className="mt-2.5 flex items-center gap-2 text-[0.68rem] text-(--sim-muted-foreground)">
        <Pill tone={tone}>
          {status === 'queued'
            ? 'Na fila'
            : status === 'working'
              ? 'Trabalhando'
              : status === 'done'
                ? variation.position
                  ? `rev ${variation.position}`
                  : 'Pronta'
                : status === 'refused'
                  ? 'Recusada'
                  : 'Interrompida'}
        </Pill>
      </div>
    </>
  )
}

/** Um nó do grafo da exploração: partida, rodada do explorador, variação ou relatório. */
export function ExplorationNode({ data }: NodeProps<ExplorationFlowNode>) {
  const { node, simulationId } = data

  if (node.kind === 'start') {
    return (
      <Shell tone="done" label="Revisão de partida">
        <Head
          icon={<Route className="size-4" />}
          title="Revisão de partida"
          subtitle="De onde a exploração parte"
        />
        <p className="mt-2.5 text-xs">
          <Link
            to={`/simulacoes/${node.revisionId}`}
            className="nodrag nopan cursor-pointer font-semibold text-(--sim-brand) hover:underline"
          >
            Abrir a revisão
          </Link>
        </p>
      </Shell>
    )
  }

  if (node.kind === 'round') {
    const { status } = node.round
    const thinking = status === 'thinking'
    return (
      <Shell
        tone={thinking ? 'working' : status === 'ended' ? 'idle' : 'done'}
        dashed={status === 'ended'}
        label={`Rodada ${node.round.number}`}
      >
        <Head
          icon={<span className="text-xs font-bold">{node.round.number}</span>}
          title={`Rodada ${node.round.number}`}
          subtitle={
            thinking
              ? 'Explorador decidindo'
              : status === 'ended'
                ? 'Explorador encerrou'
                : 'Explorador decidiu'
          }
          spinning={thinking}
        />
        {thinking || status === 'ended' ? (
          <p className="mt-2.5 text-xs text-(--sim-muted-foreground)">
            {thinking ? 'Lendo os resultados…' : 'Nenhuma variação decidida nesta rodada.'}
          </p>
        ) : (
          <p className="mt-2.5 line-clamp-4 text-xs leading-5" title={node.round.why}>
            {node.round.why}
          </p>
        )}
      </Shell>
    )
  }

  if (node.kind === 'variation') {
    const { status } = node.variation
    const tone: Tone =
      status === 'working'
        ? 'working'
        : status === 'done'
          ? 'done'
          : status === 'refused'
            ? 'failed'
            : 'idle'
    return (
      <Shell
        tone={tone}
        dashed={status === 'queued' || status === 'interrupted'}
        label={`${leverLabel(node.variation.lever)} ${leverValue(node.variation.lever, node.variation.value)}`}
      >
        <VariationBody variation={node.variation} />
        {status === 'done' && node.variation.revisionId != null && (
          <p className="mt-2 text-xs">
            <Link
              to={`/simulacoes/${node.variation.revisionId}`}
              className="nodrag nopan cursor-pointer font-semibold text-(--sim-brand) hover:underline"
            >
              Abrir a revisão
            </Link>
          </p>
        )}
      </Shell>
    )
  }

  const { report } = node
  const tone: Tone =
    report.state === 'gerando' ? 'working' : report.state === 'pronto' ? 'done' : 'failed'
  return (
    <Shell tone={tone} label="Relatório">
      <Head
        icon={<FileText className="size-4" />}
        title="Relatório"
        subtitle="A leitura da exploração"
        spinning={report.state === 'gerando'}
      />
      <div className="mt-2.5 flex items-center gap-3 text-xs">
        <Pill tone={tone}>{reportLabels[report.state]}</Pill>
        {report.state !== 'gerando' && (
          <Link
            to={`/simulacoes/${simulationId}/relatorios/${report.id}`}
            className="nodrag nopan cursor-pointer font-semibold text-(--sim-brand) hover:underline"
          >
            Abrir o relatório
          </Link>
        )}
      </div>
    </Shell>
  )
}
