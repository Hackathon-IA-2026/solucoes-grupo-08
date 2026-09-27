import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import type { FullRevision } from '../../api/get-simulation'
import { modalityLabels } from '../../api/labels'
import { ExplorationsDialog } from '@/features/agents/components/explorations-dialog'
import { ReportsDialog } from '../report/reports-dialog'
import { Breadcrumbs } from '@/components/layout/breadcrumbs'
import { InfoTooltip } from '@/components/ui/tooltip'
import { formatDate, formatPeriod, formatSnapshotId } from '@/utils/format'

type ResultHeaderProps = {
  revision: FullRevision
  /** Texto do ONS da restrição, do cadastro. Chega depois do resto da tela. */
  restrictionText?: string
}

const container = 'mx-auto max-w-screen-2xl px-4 sm:px-6 lg:px-8'

/** As duas faixas do topo, de ponta a ponta da tela: título e ações, e a pergunta com a revisão. */
export function ResultHeader({ revision, restrictionText }: ResultHeaderProps) {
  const navigate = useNavigate()
  const [explorationsOpen, setExplorationsOpen] = useState(false)
  const [reportsOpen, setReportsOpen] = useState(false)
  const position = revision.revisoes.find((sibling) => sibling.id === revision.id)
  const modality = modalityLabels[revision.configuracao.modalidade]

  return (
    <>
      <section className="border-b border-(--sim-border) bg-(--sim-background)">
        <div className={`${container} py-6`}>
          <Breadcrumbs
            className="mb-4"
            items={[{ label: 'Simulações', to: '/simulacoes' }, { label: revision.nome }]}
          />
          <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <span className="sim-chip">{modality}</span>
                <span className="text-xs text-(--sim-muted-foreground)">
                  Criada em {formatDate(revision.criada_em)}
                </span>
              </div>
              <h1 className="sim-display max-w-4xl text-3xl font-semibold leading-tight text-(--sim-brand-ink) sm:text-4xl">
                {revision.nome}
              </h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="sim-btn-secondary"
                onClick={() => setExplorationsOpen(true)}
              >
                Explorações
              </button>
              <ExplorationsDialog
                open={explorationsOpen}
                onOpenChange={setExplorationsOpen}
                simulationId={revision.simulacao_id}
                revisionId={revision.id}
              />
              <button
                type="button"
                className="sim-btn-primary"
                onClick={() => setReportsOpen(true)}
              >
                Relatórios
              </button>
              <ReportsDialog
                open={reportsOpen}
                onOpenChange={setReportsOpen}
                simulationId={revision.simulacao_id}
              />
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-(--sim-border) bg-(--sim-surface)">
        <div className={`${container} grid grid-cols-1 gap-4 py-5 lg:grid-cols-12`}>
          <article className="sim-decision flex flex-col lg:col-span-6">
            <span className="sim-eyebrow mb-3 text-(--sim-sky-soft)">
              {revision.pergunta ? 'Pergunta decisória' : 'Restrição'}
            </span>
            {revision.pergunta && (
              <p className="sim-display text-lg font-medium leading-snug">{revision.pergunta}</p>
            )}
            <Link
              to={`/restricoes/${revision.restricao_id}`}
              title={restrictionText}
              className={`text-xs leading-5 text-(--sim-brand-foreground)/70 hover:underline ${revision.pergunta ? 'mt-3' : ''}`}
            >
              {restrictionText ?? `restrição ${revision.restricao_id}`}
            </Link>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="sim-decision-tag">{modality}</span>
            </div>
          </article>

          <article className="sim-summary lg:col-span-3">
            <label
              htmlFor="revisao"
              className="sim-eyebrow flex items-center gap-1.5 text-(--sim-muted-foreground)"
            >
              Revisão
              <InfoTooltip label="Ajuda: Revisão">
                Cada cálculo salvo da simulação. Alterar um parâmetro e recalcular cria uma revisão
                nova ligada à anterior; nada se apaga. &quot;Atual&quot; é a mais recente.
              </InfoTooltip>
            </label>
            <select
              id="revisao"
              value={revision.id}
              onChange={(event) => navigate(`/simulacoes/${event.target.value}`)}
              className="mt-3 h-10 w-full rounded-md border border-(--sim-border) bg-(--sim-background) px-3 text-sm font-semibold text-(--sim-brand-ink) outline-none focus:ring-2 focus:ring-(--sim-ring)"
            >
              {revision.revisoes.map((sibling) => (
                <option key={sibling.id} value={sibling.id}>
                  rev {sibling.posicao}
                  {sibling.atual ? ' · atual' : ''} · {formatDate(sibling.criada_em)}
                </option>
              ))}
            </select>
            {position && (
              <p className="mt-3 text-xs leading-5 text-(--sim-muted-foreground)">
                Visualizando a revisão {position.posicao}.{' '}
                <span className="inline-flex items-center gap-1">
                  Dado ONS versão {formatSnapshotId(revision.snapshot_id)}
                  <InfoTooltip label="Ajuda: dado ONS versão">
                    Snapshot: cópia datada e imutável dos arquivos do ONS usada neste cálculo.
                    Nenhum cálculo lê o dado ao vivo.
                  </InfoTooltip>
                </span>{' '}
                ·{' '}
                <span className="inline-flex items-center gap-1">
                  método v{revision.metodo_versao}
                  <InfoTooltip label="Ajuda: método v">
                    Versão do conjunto de regras de cálculo. Sobe quando uma regra ou premissa
                    padrão muda e o resultado passa a ser diferente para a mesma entrada.
                  </InfoTooltip>
                </span>
              </p>
            )}
          </article>

          <article className="sim-summary lg:col-span-3">
            <p className="sim-eyebrow text-(--sim-muted-foreground)">Janela analisada</p>
            <strong className="sim-display mt-2 block text-base text-(--sim-brand-ink)">
              {formatPeriod(revision.periodo_inicio, revision.periodo_fim)}
            </strong>
          </article>
        </div>
      </section>
    </>
  )
}
