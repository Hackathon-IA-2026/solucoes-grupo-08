import { Building2, Gauge, MapPin, Ruler, Zap } from 'lucide-react'
import type { ComponentType } from 'react'
import type { DetailedRestriction } from '../api/get-restriction'
import { InfoTooltip, Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatInteger } from '@/utils/format'

type RestrictionEquipmentProps = {
  item: DetailedRestriction
}

const roleLabels: Record<string, string> = {
  monitorado: 'monitorado',
  contingenciado: 'contingenciado',
}

const feminineRoles: Record<string, string> = {
  monitorado: 'monitorada',
  contingenciado: 'contingenciada',
}

const roleTooltips: Record<string, string> = {
  monitorado:
    'Papel da linha dentro da restrição. Monitorado é a linha cujo fluxo o ONS vigia e limita; é dela que a restrição trata. Vem do texto do ONS, não do cadastro.',
  contingenciado:
    'Linha cuja perda a restrição supõe: o limite vale para o caso de ela sair de operação. Duas restrições sobre a mesma linha monitorada se distinguem pela contingência.',
}

/** Uma linha por cartão: nome, papel e as especificações do cadastro do ONS. */
export function RestrictionEquipment({ item }: RestrictionEquipmentProps) {
  return (
    <>
      {item.equipamentos.map((equipment) => (
        <section key={equipment.cod_equipamento} className="sim-card mt-5">
          <div className="sim-card-head flex flex-col gap-2 border-b border-(--sim-border) px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="sim-eyebrow text-(--sim-brand)">
                Linha {feminineRoles[equipment.papel] ?? equipment.papel}
              </p>
              <h2 className="sim-display mt-1 text-base font-semibold text-(--sim-brand-ink)">
                {equipment.nome ?? equipment.cod_equipamento}
              </h2>
            </div>
            <Tooltip>
              {/* O gatilho é este span, focável, com a etiqueta dentro. */}
              <TooltipTrigger asChild>
                <span tabIndex={0} className="sim-tag w-fit normal-case">
                  Papel: {roleLabels[equipment.papel] ?? equipment.papel}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {roleTooltips[equipment.papel] ?? 'Papel da linha dentro da restrição.'}
              </TooltipContent>
            </Tooltip>
          </div>

          <div className="grid grid-cols-2 divide-x divide-y divide-(--sim-border) lg:grid-cols-6 lg:divide-y-0">
            <Spec
              icon={Zap}
              label="Tensão"
              value={equipment.tensao_kv ? `${equipment.tensao_kv} kV` : '[n/d]'}
            />
            <Spec icon={MapPin} label="Subestação A" value={equipment.subestacao_de ?? '[n/d]'} />
            <Spec icon={MapPin} label="Subestação B" value={equipment.subestacao_para ?? '[n/d]'} />
            <Spec
              icon={Ruler}
              label="Comprimento"
              value={
                equipment.comprimento_km
                  ? `${formatInteger(equipment.comprimento_km)} km`
                  : 'sem cadastro'
              }
              warn={!equipment.comprimento_km}
            />
            <Spec
              icon={Gauge}
              label="Capacidade longa"
              value={
                equipment.capacidade_longa_mva
                  ? `${formatInteger(equipment.capacidade_longa_mva)} MVA`
                  : 'sem cadastro'
              }
              warn={!equipment.capacidade_longa_mva}
              tooltip="Capacidade operativa de longa duração sem limitação, em MVA, do cadastro do ONS. É contexto: em várias restrições do escopo o limite que corta é de tensão, não de capacidade, e este número não entra no cálculo."
            />
            <Spec
              icon={Building2}
              label="Proprietário"
              value={equipment.proprietario ?? 'sem cadastro'}
              warn={!equipment.proprietario}
            />
          </div>
        </section>
      ))}
    </>
  )
}

type SpecProps = {
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' }>
  label: string
  value: string
  warn?: boolean
  tooltip?: string
}

function Spec({ icon: Icon, label, value, warn = false, tooltip }: SpecProps) {
  return (
    <div className="min-h-24 p-4">
      <div className="flex items-center gap-1.5 text-(--sim-muted-foreground)">
        <Icon className="size-3.5 text-(--sim-brand)" aria-hidden="true" />
        <span className="text-[10px] font-extrabold uppercase">{label}</span>
        {tooltip && <InfoTooltip label={`Ajuda: ${label}`}>{tooltip}</InfoTooltip>}
      </div>
      <strong
        className={
          warn
            ? 'mt-2 block text-xs font-bold text-warning sm:text-sm'
            : 'mt-2 block text-xs font-bold text-(--sim-brand-ink) sm:text-sm'
        }
      >
        {value}
      </strong>
    </div>
  )
}
