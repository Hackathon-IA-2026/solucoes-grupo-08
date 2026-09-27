import '@xyflow/react/dist/style.css'
import {
  applyNodeChanges,
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useStore,
  useStoreApi,
  type Edge,
  type NodeChange,
} from '@xyflow/react'
import { useQueryClient } from '@tanstack/react-query'
import { shallow as shallowEqual } from 'zustand/shallow'
import { Crosshair } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { taskQueryOptions, useTask, type TaskState } from '@/features/agents/api/exploration'
import { buildGraph, type EdgeStatus, type NodeHeights } from '@/features/agents/api/graph'
import { NODE_HEIGHT, NODE_WIDTH } from '@/features/agents/api/layout'
import { useRevealQueue } from '@/features/agents/api/use-reveal-queue'
import { useExplorationStream, type Connection } from '@/features/agents/api/use-exploration-stream'
import {
  ExplorationNode,
  type ExplorationFlowNode,
} from '@/features/agents/components/exploration-node'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/utils/cn'
import { formatInteger } from '@/utils/format'

const nodeTypes = { exploration: ExplorationNode }

/** Folga entre o desenho e a borda da área, em pixels de tela. */
const VIEW_PADDING = 24

const stateLabels: Record<TaskState, string> = {
  em_andamento: 'Em andamento',
  concluida: 'Concluída',
  falhou: 'Falhou',
}

const connectionLabels: Record<Connection, string> = {
  connecting: 'Conectando',
  live: 'Ao vivo',
  reconnecting: 'Reconectando',
  closed: 'Encerrada',
}

// Os eventos que mudam a contagem ou o estado da exploração: a API é quem conta.
const REFRESH_ON = new Set([
  'variacao_iniciada',
  'revisao_pronta',
  'variacao_recusada',
  'relatorio_pedido',
  'tarefa_terminada',
])

const edgeStyles: Record<
  EdgeStatus,
  { stroke: string; strokeDasharray?: string; opacity?: number }
> = {
  queued: { stroke: 'var(--sim-muted-foreground)', strokeDasharray: '4 5', opacity: 0.6 },
  working: { stroke: 'var(--sim-brand)' },
  done: { stroke: 'var(--sim-positive)', opacity: 0.75 },
  refused: { stroke: 'var(--color-danger)', strokeDasharray: '4 5' },
  idle: { stroke: 'var(--sim-muted-foreground)', strokeDasharray: '4 5', opacity: 0.4 },
}

function clock(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

export default function SimulationExploration() {
  const { tarefaId } = useParams()
  return (
    <ReactFlowProvider>
      <ExplorationPage key={tarefaId} />
    </ReactFlowProvider>
  )
}

function ExplorationPage() {
  const { simulacaoId, tarefaId } = useParams()
  const simulationId = Number(simulacaoId)
  const taskId = Number(tarefaId)
  const queryClient = useQueryClient()
  const taskQuery = useTask(taskId)
  // Ao conectar a API reenvia tudo o que já gravou, em rajada: uma leitura só no fim da rajada.
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(refreshTimer.current), [])
  const { state, connection } = useExplorationStream(taskId, (event) => {
    if (!REFRESH_ON.has(event.tipo)) return
    clearTimeout(refreshTimer.current)
    refreshTimer.current = setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: taskQueryOptions(taskId).queryKey })
    }, 300)
  })
  const { setViewport } = useReactFlow()
  const storeApi = useStoreApi()
  const [follow, setFollow] = useState(true)
  // Altura real de cada cartão, medida pelo React Flow: o layout reserva a faixa de cada um com
  // ela, e não com uma estimativa (uma variação recusada, por exemplo, traz o motivo por extenso).
  const [heights, setHeights] = useState<NodeHeights>({})
  const graph = useMemo(
    () => buildGraph(state, taskQuery.data, heights),
    [state, taskQuery.data, heights],
  )
  const finished = state.finished !== null

  // Os cartões entram um por vez, cada um com a ligação que o prende ao anterior, e não todos de
  // uma vez. O layout já conhece todos, então os que entram não empurram os que estavam na tela.
  const { revealed, waiting } = useRevealQueue(graph.nodes)
  const shown = useMemo(() => {
    const nodes = graph.nodes.filter((node) => revealed.has(node.id))
    return {
      nodes,
      edges: graph.edges.filter((edge) => revealed.has(edge.source) && revealed.has(edge.target)),
      // O nó ativo só vale depois de aparecer; até lá a câmera acompanha o último que entrou.
      activeId:
        graph.activeId && revealed.has(graph.activeId)
          ? graph.activeId
          : (nodes.at(-1)?.id ?? null),
    }
  }, [graph, revealed])

  // Os nós vivem em estado próprio (padrão controlado do React Flow): recriá-los a cada render
  // apaga o tamanho medido, e o arrasto entra em laço de medição. Ao mudar o grafo, o que já
  // existe mantém a posição atual (a que a pessoa arrastou) e o tamanho medido.
  const [nodes, setNodes] = useState<ExplorationFlowNode[]>([])
  const [syncedGraph, setSyncedGraph] = useState<typeof shown | null>(null)
  if (syncedGraph !== shown) {
    setSyncedGraph(shown)
    setNodes((current) => {
      const byId = new Map(current.map((node) => [node.id, node]))
      return shown.nodes.map((node) => {
        const existing = byId.get(node.id)
        return {
          ...existing,
          id: node.id,
          type: 'exploration',
          position: node.position,
          data: { node, simulationId },
        }
      })
    })
  }
  const onNodesChange = useCallback((changes: NodeChange<ExplorationFlowNode>[]) => {
    setNodes((current) => applyNodeChanges(changes, current))
    // Só quando a altura muda de verdade: reposicionar não altera o tamanho, e assim medir não
    // volta a disparar o layout.
    const measured = changes.flatMap((change) =>
      change.type === 'dimensions' && change.dimensions
        ? [[change.id, Math.round(change.dimensions.height)] as const]
        : [],
    )
    if (measured.length > 0) {
      setHeights((current) =>
        measured.every(([id, height]) => current[id] === height)
          ? current
          : { ...current, ...Object.fromEntries(measured) },
      )
    }
  }, [])
  const edges = useMemo<Edge[]>(
    () =>
      shown.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        animated: edge.status === 'working',
        style: { strokeWidth: 1.8, ...edgeStyles[edge.status] },
      })),
    [shown],
  )

  // A altura do desenho sempre cabe na tela; só a largura rola. O zoom sai da altura do desenho
  // (o maior bloco de agentes) contra a da área, e nunca passa de 1.
  const [viewWidth, viewHeight] = useStore((store) => [store.width, store.height], shallowEqual)
  const graphHeight = useMemo(
    () =>
      Math.max(
        NODE_HEIGHT,
        ...graph.nodes.map((node) => node.position.y + (heights[node.id] ?? NODE_HEIGHT)),
      ),
    [graph, heights],
  )
  const fitZoom = viewHeight > 0 ? Math.min(1, (viewHeight - 2 * VIEW_PADDING) / graphHeight) : 1
  const graphWidth = useMemo(
    () => Math.max(NODE_WIDTH, ...shown.nodes.map((node) => node.position.x + NODE_WIDTH)),
    [shown],
  )
  // Onde a rolagem para: da folga à esquerda até o fim do último cartão, também com folga. O
  // `setViewport` não respeita o `translateExtent` (só o arrasto e o `panBy` respeitam), então o
  // limite vale aqui também, senão a câmera passaria do fim do desenho.
  const minX = Math.min(VIEW_PADDING, viewWidth - graphWidth * fitZoom - VIEW_PADDING)
  const viewportAt = useCallback(
    (left: number) => ({
      // Folga à esquerda: o primeiro cartão não encosta na borda da área.
      x: Math.max(minX, VIEW_PADDING - Math.max(0, left * fitZoom)),
      // Desenho mais baixo que a área fica no meio dela; mais alto, encosta no topo com folga.
      y: Math.max(VIEW_PADDING, (viewHeight - graphHeight * fitZoom) / 2),
      zoom: fitZoom,
    }),
    [fitZoom, viewHeight, graphHeight, minX],
  )

  const translateExtent = useMemo<[[number, number], [number, number]]>(
    () => [
      [-VIEW_PADDING / fitZoom, -VIEW_PADDING / fitZoom],
      [graphWidth + VIEW_PADDING / fitZoom, graphHeight + VIEW_PADDING / fitZoom],
    ],
    [graphWidth, graphHeight, fitZoom],
  )
  // A roda do mouse rola na horizontal (o gesto de trackpad já entrega o deslocamento lateral).
  // Pelo `panBy`, que respeita o `translateExtent`: parar no fim do desenho, e não seguir adiante.
  const scrollSideways = (event: React.WheelEvent) => {
    const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
    void storeApi.getState().panBy({ x: -delta, y: 0 })
  }

  // Seguir: a câmera rola até o nó ativo, deixando-o a um terço da largura, sem mexer na escala.
  // Só quando ele muda, e não a cada evento, senão a tela treme a cada passo. A posição vem do
  // layout, porque o nó recém-chegado ainda não foi medido quando o efeito roda.
  const shownRef = useRef(shown)
  useEffect(() => {
    shownRef.current = shown
  }, [shown])
  useEffect(() => {
    if (!follow || !shown.activeId || viewWidth === 0) return
    const active = shownRef.current.nodes.find((node) => node.id === shownRef.current.activeId)
    if (!active) return
    void setViewport(viewportAt(active.position.x - (viewWidth * 0.35) / fitZoom), {
      duration: 600,
    })
  }, [follow, shown.activeId, setViewport, viewportAt, viewWidth, fitZoom])

  // Ao terminar, com o Seguir ligado, a câmera volta ao começo do desenho, na mesma escala.
  const allShown = graph.nodes.length > 0 && waiting === 0
  useEffect(() => {
    if (!finished || !follow || !allShown || viewWidth === 0) return
    void setViewport(viewportAt(0), { duration: 800 })
  }, [finished, follow, allShown, setViewport, viewportAt, viewWidth])

  const running = taskQuery.data?.estado === 'em_andamento'
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])

  if (taskQuery.isPending) {
    return (
      <div className="sim-page flex justify-center px-6 py-16">
        <Spinner />
      </div>
    )
  }

  if (taskQuery.isError) {
    return (
      <div className="sim-page">
        <div className="mx-auto max-w-screen-2xl px-4 py-8 sm:px-6 lg:px-8">
          <p role="alert" className="text-sm text-warning">
            Não foi possível carregar a exploração: {taskQuery.error.message}
          </p>
          <Link to="/simulacoes" className="sim-btn-secondary mt-4">
            Voltar para Simulações
          </Link>
        </div>
      </div>
    )
  }

  const task = taskQuery.data
  const counts = task.contagem
  const elapsed =
    (task.terminada_em ? Date.parse(task.terminada_em) : now) - Date.parse(task.criada_em)

  return (
    <div className="sim-page flex h-[calc(100dvh-4rem)] min-h-0! flex-col">
      <section className="border-b border-(--sim-border)">
        <div className="mx-auto flex max-w-screen-2xl flex-col gap-x-8 gap-y-2 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-x-2.5">
              <span className="sim-eyebrow shrink-0 text-(--sim-brand)">
                Exploração com agentes
              </span>
              <span
                className={cn(
                  'shrink-0 rounded-full px-2 py-0.5 text-[0.7rem] font-semibold',
                  task.estado === 'em_andamento' && 'bg-(--sim-sky-soft) text-(--sim-brand)',
                  task.estado === 'concluida' && 'bg-success-light text-success',
                  task.estado === 'falhou' && 'bg-danger-light text-danger',
                )}
              >
                {stateLabels[task.estado]}
              </span>
              <span
                className="shrink-0 text-[0.7rem] text-(--sim-muted-foreground)"
                aria-live="polite"
              >
                {connectionLabels[connection]}
              </span>
            </div>
            {/* Uma linha só cada: o texto inteiro está no tooltip, e o espaço é do grafo. */}
            <h1
              title={task.pedido}
              className="sim-display truncate text-base font-semibold text-(--sim-brand-ink) sm:text-lg"
            >
              {task.pedido}
            </h1>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-x-5 gap-y-2">
            <dl className="flex flex-wrap gap-x-4 gap-y-1 tabular-nums" aria-live="polite">
              <Counter label="Rodadas" value={counts.rodadas} />
              <Counter label="Disparadas" value={counts.disparadas} />
              <Counter label="Trabalhando" value={counts.trabalhando} />
              <Counter
                label="Prontas"
                value={counts.prontas}
                suffix={`de ${formatInteger(task.teto)}`}
              />
              <Counter label="Recusadas" value={counts.recusadas} />
              {counts.interrompidas > 0 && (
                <Counter label="Interrompidas" value={counts.interrompidas} />
              )}
            </dl>
            <div className="flex items-center gap-2">
              <span className="min-w-10 text-right text-xs font-semibold tabular-nums text-(--sim-muted-foreground)">
                {clock(elapsed)}
              </span>
              <button
                type="button"
                aria-pressed={follow}
                onClick={() => setFollow((value) => !value)}
                className={cn(
                  'sim-btn-secondary gap-1.5',
                  follow && 'border-(--sim-brand)! text-(--sim-brand)!',
                )}
              >
                <Crosshair className="size-4" aria-hidden="true" />
                Seguir
              </button>
              {task.relatorio_id != null && (
                <Link
                  to={`/simulacoes/${task.simulacao_id}/relatorios/${task.relatorio_id}`}
                  className="sim-btn-primary"
                >
                  Abrir o relatório
                </Link>
              )}
            </div>
          </div>
        </div>
      </section>

      <div className="flex min-h-0 w-full flex-1 flex-col">
        <section
          aria-label="Agentes em execução"
          // Um gesto do usuário no canvas desliga o Seguir. O onMoveStart do React Flow não serve:
          // ele também dispara quando quem move a câmera é o próprio Seguir.
          onWheel={(event) => {
            setFollow(false)
            scrollSideways(event)
          }}
          onPointerDown={() => setFollow(false)}
          onContextMenu={(event) => event.preventDefault()}
          className="relative min-h-80 flex-1 bg-(--sim-background)"
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            nodesDraggable={false}
            onNodesChange={onNodesChange}
            zoomOnScroll={false}
            zoomOnPinch={false}
            zoomOnDoubleClick={false}
            minZoom={fitZoom}
            maxZoom={fitZoom}
            translateExtent={translateExtent}
            nodesConnectable={false}
            elementsSelectable={false}
            defaultViewport={{ x: VIEW_PADDING, y: VIEW_PADDING, zoom: 1 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={22}
              size={1.2}
              color="var(--sim-border)"
            />
          </ReactFlow>
        </section>
      </div>
    </div>
  )
}

function Counter({ label, value, suffix }: { label: string; value: number; suffix?: string }) {
  return (
    <div className="grid">
      <dt className="sim-overview-label">{label}</dt>
      <dd className="sim-display text-lg font-semibold leading-tight text-(--sim-brand-ink)">
        {formatInteger(value)}
        {suffix && (
          <span className="ml-1 text-[0.7rem] font-normal text-(--sim-muted-foreground)">
            {suffix}
          </span>
        )}
      </dd>
    </div>
  )
}
