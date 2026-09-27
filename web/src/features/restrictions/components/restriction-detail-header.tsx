import { ArrowUpRight, Plus } from 'lucide-react'
import { Link } from 'react-router'
import type { DetailedRestriction } from '../api/get-restriction'
import { sourceLabels } from '../api/get-restrictions'
import { InfoTooltip } from '@/components/ui/tooltip'
import { truncateText } from '@/utils/format'

type RestrictionDetailHeaderProps = {
  item: DetailedRestriction
}

/** O topo do cartão da restrição: identificação, texto original do ONS e as duas ações. */
export function RestrictionDetailHeader({ item }: RestrictionDetailHeaderProps) {
  const title = item.nome_curto ?? truncateText(item.texto, 90)

  return (
    <header className="sim-card-head flex flex-col gap-5 border-b border-(--sim-border) px-5 py-5 lg:flex-row lg:items-center lg:justify-between lg:px-7">
      <div className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <span className="sim-tag inline-flex items-center gap-1">
            {item.instrucao_operacao ?? 'sem IO'}
            <InfoTooltip label="Ajuda: IO">
              Instrução de Operação: documento do ONS que fixa limites e procedimentos de uma área
              ou instalação. O código, como IO-ON.NE.5NE, é o que o operador usa para achar a regra.
            </InfoTooltip>
          </span>
          <span className="flex flex-wrap items-center gap-x-1.5 text-xs font-semibold text-(--sim-muted-foreground)">
            <span className="inline-flex items-center gap-1">
              Origem {item.origem}
              <InfoTooltip label="Ajuda: origem">
                Origem da restrição no dado do ONS. LOC é local: o corte atinge um conjunto
                específico de usinas atrás de um equipamento. A alternativa, SIS, é sistêmica e
                rateada entre todas as usinas; o ARCO só trata LOC.
              </InfoTooltip>
            </span>
            ·
            <span className="inline-flex items-center gap-1">
              Razão {item.razao}
              <InfoTooltip label="Ajuda: razão">
                Motivo do corte no dado do ONS. CNF é confiabilidade elétrica: segurança da operação
                da rede. As outras razões são REL (equipamento de transmissão indisponível) e ENE
                (excedente de energia). O ARCO só trata CNF.
              </InfoTooltip>
            </span>
            ·<span>Fonte {sourceLabels[item.fonte]}</span>
          </span>
        </div>

        <h1
          className="sim-display text-xl font-semibold text-(--sim-brand-ink) sm:text-2xl"
          title={item.texto}
        >
          {title}
        </h1>

        <details className="mt-2 max-w-4xl text-xs leading-5 text-(--sim-muted-foreground)">
          <summary className="cursor-pointer font-semibold text-(--sim-brand-ink)">
            Texto original do ONS
          </summary>
          <p className="mt-2">{item.texto}</p>
        </details>
      </div>

      <div className="flex shrink-0 flex-wrap gap-2">
        <Link
          to={{
            pathname: '/simulacoes',
            search: new URLSearchParams({ restricao: item.id, nome: title }).toString(),
          }}
          className="sim-btn-secondary gap-1.5"
        >
          Ver simulações
          <ArrowUpRight className="size-4" aria-hidden="true" />
        </Link>
        <Link to={`/restricoes/${item.id}/nova-simulacao`} className="sim-btn-primary gap-1.5">
          <Plus className="size-4" aria-hidden="true" />
          Criar simulação
        </Link>
      </div>
    </header>
  )
}
