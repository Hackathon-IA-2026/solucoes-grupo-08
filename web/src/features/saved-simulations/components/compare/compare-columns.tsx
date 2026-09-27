import { Link } from 'react-router'
import type { FullRevision } from '../../api/get-simulation'
import { InfoTooltip } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'
import { formatDate, formatPeriod, formatSnapshotId } from '@/utils/format'

type CompareColumnProps = {
  letter: 'A' | 'B'
  revision: FullRevision
  /** O snapshot ou o método desta revisão difere do da outra. */
  differsFromOther: boolean
}

function CompareColumn({ letter, revision, differsFromOther }: CompareColumnProps) {
  const position = revision.revisoes.find((sibling) => sibling.id === revision.id)

  return (
    <article className="sim-card min-w-0">
      <div className="sim-card-head flex items-center gap-3 border-b border-(--sim-border) px-5 py-4">
        <span className="sim-rank-number">{letter}</span>
        <Link
          to={`/simulacoes/${revision.id}`}
          className="sim-display min-w-0 text-base font-semibold text-(--sim-brand-ink) hover:text-(--sim-brand)"
        >
          {revision.nome}
        </Link>
      </div>
      <dl className="grid gap-3 px-5 py-4 text-xs">
        <div className="flex items-baseline justify-between gap-4">
          <dt className="text-(--sim-muted-foreground)">Revisão</dt>
          <dd className="font-bold text-(--sim-brand-ink)">
            rev {position?.posicao ?? '?'}
            {position?.atual ? ', atual' : ''} · {formatDate(revision.criada_em)}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-4">
          <dt className="text-(--sim-muted-foreground)">Dado ONS · método</dt>
          <dd
            className={cn(
              'flex flex-wrap items-center justify-end gap-x-1 text-right font-bold text-(--sim-brand-ink)',
              differsFromOther && 'text-warning',
            )}
          >
            <span className="inline-flex items-center gap-1">
              ONS versão {formatSnapshotId(revision.snapshot_id)}
              <InfoTooltip label="Ajuda: ONS versão">
                Snapshot: cópia datada e imutável dos arquivos do ONS usada neste cálculo. Nenhum
                cálculo lê o dado ao vivo.
              </InfoTooltip>
            </span>
            ·
            <span className="inline-flex items-center gap-1">
              método v{revision.metodo_versao}
              <InfoTooltip label="Ajuda: método v">
                Versão do conjunto de regras de cálculo. Sobe quando uma regra ou premissa padrão
                muda e o resultado passa a ser diferente para a mesma entrada.
              </InfoTooltip>
            </span>
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-4">
          <dt className="text-(--sim-muted-foreground)">Janela</dt>
          <dd className="font-bold text-(--sim-brand-ink)">
            {formatPeriod(revision.periodo_inicio, revision.periodo_fim)}
          </dd>
        </div>
      </dl>
    </article>
  )
}

/** As duas revisões, com o que as identifica, lado a lado na largura toda. */
export function CompareColumns({ a, b }: { a: FullRevision; b: FullRevision }) {
  const differs = a.snapshot_id !== b.snapshot_id || a.metodo_versao !== b.metodo_versao

  return (
    <div className="grid items-stretch gap-4 md:grid-cols-2">
      <CompareColumn letter="A" revision={a} differsFromOther={differs} />
      <CompareColumn letter="B" revision={b} differsFromOther={differs} />
    </div>
  )
}
