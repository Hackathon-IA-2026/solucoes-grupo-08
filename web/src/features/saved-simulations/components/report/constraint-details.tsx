import { CalendarDays, Info } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ReportHeader } from '../../api/report'
import {
  capitalizeFirst,
  formatDate,
  formatInteger,
  formatNumber,
  formatPeriod,
  formatSnapshotId,
} from '@/utils/format'

const linkProvenance: Record<string, string> = {
  automatica: 'Histórico do ONS',
  por_modelo: 'Extraído por modelo',
  por_pessoa: 'Informado por pessoa',
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="mb-1 text-xs text-(--sim-muted-foreground)">{label}</dt>
      <dd className="text-sm font-semibold text-(--sim-brand-ink)">{children}</dd>
    </div>
  )
}

function Terminals({ from, to }: { from?: string | null; to?: string | null }) {
  return <>{[from, to].filter(Boolean).join(' – ') || '—'}</>
}

/** A restrição como estava no snapshot: identidade, equipamentos, maiores ocorrências. */
export function ConstraintDetails({ header }: { header: ReportHeader }) {
  const occurrences = header.ocorrencias
  const largest = Math.max(0, ...occurrences.maiores.map((occurrence) => occurrence.energia_mwh))

  return (
    <article className="sim-panel flex min-w-0 flex-col gap-5 p-6!">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <h3 className="sim-display text-base font-semibold text-(--sim-brand-ink)">
            A restrição e o período
          </h3>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-(--sim-muted) px-2.5 py-1 text-xs text-(--sim-foreground)">
          <CalendarDays className="size-3.5" aria-hidden="true" />
          {formatPeriod(header.periodo_inicio, header.periodo_fim)}
        </span>
      </div>

      <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Nome curto">{header.nome_curto ?? '—'}</Field>
        <Field label="Instrução de Operação">
          <span className="font-mono font-medium">{header.instrucao_operacao ?? '—'}</span>
        </Field>
        <Field label="Subestações">{header.subestacoes.join(' – ')}</Field>
        <Field label="Contingência">
          {header.contingencia ?? (
            <span className="font-normal text-(--sim-muted-foreground)">Nenhuma registrada</span>
          )}
        </Field>
        <Field label="Presente no snapshot">
          {header.presente_no_snapshot ? (
            <span className="text-success">Sim</span>
          ) : (
            <span className="text-warning">Não</span>
          )}{' '}
          <span className="font-normal tabular-nums text-(--sim-muted-foreground)">
            · {formatSnapshotId(header.snapshot_id)}
          </span>
        </Field>
        <Field label="Avisos">
          {header.avisos.length === 0 ? (
            <span className="font-normal text-(--sim-foreground)">
              Sem aviso de tensão ou obra gravado
            </span>
          ) : (
            <ul className="flex flex-col gap-1 font-medium text-warning">
              {header.avisos.map((warning) => (
                <li key={warning.codigo}>{warning.mensagem}</li>
              ))}
            </ul>
          )}
        </Field>
      </dl>

      <div className="flex flex-col gap-2">
        <h4 className="text-xs font-semibold text-(--sim-foreground)">Equipamento</h4>
        {/* Tabela sem rolagem lateral no desktop; no celular cada equipamento vira um cartão. */}
        <ul className="flex flex-col gap-2 sm:hidden">
          {header.equipamentos.map((row) => (
            <li
              key={row.cod_equipamento}
              className="rounded-lg border border-(--sim-border) p-3 text-xs"
            >
              <p className="font-semibold text-(--sim-brand-ink)">
                {row.nome ?? row.cod_equipamento}
              </p>
              <p className="mt-1 text-(--sim-muted-foreground)">
                {capitalizeFirst(row.papel)} ·{' '}
                {row.tensao_kv == null ? '—' : `${formatInteger(row.tensao_kv)} kV`} ·{' '}
                <Terminals from={row.subestacao_de} to={row.subestacao_para} />
              </p>
              <p className="mt-1 tabular-nums text-(--sim-muted-foreground)">
                {row.comprimento_km == null ? '—' : `${formatInteger(row.comprimento_km)} km`} ·{' '}
                {row.capacidade_longa_mva == null
                  ? 'capacidade sem cadastro'
                  : `${formatInteger(row.capacidade_longa_mva)} MVA`}
              </p>
            </li>
          ))}
        </ul>
        <div className="hidden overflow-hidden rounded-lg border border-(--sim-border) sm:block">
          <table className="sim-list-table w-full table-fixed text-xs">
            <thead className="bg-(--sim-background)">
              <tr>
                <th className="w-[34%]">Equipamento</th>
                <th className="w-[15%]">Papel</th>
                <th className="w-[10%]">Tensão</th>
                <th className="w-[19%]">Terminais</th>
                <th data-align="right" className="w-[11%] whitespace-normal!">
                  Compri&shy;mento
                </th>
                <th data-align="right" className="w-[11%] whitespace-normal!">
                  Capaci&shy;dade
                </th>
              </tr>
            </thead>
            <tbody>
              {header.equipamentos.map((row) => (
                <tr key={row.cod_equipamento}>
                  <td className="break-words">
                    <span className="font-semibold text-(--sim-brand-ink)">
                      {row.nome ?? row.cod_equipamento}
                    </span>
                    <span className="block text-(--sim-muted-foreground)">
                      {linkProvenance[row.procedencia] ?? row.procedencia}
                    </span>
                  </td>
                  <td>
                    <span className="sim-tag normal-case">{capitalizeFirst(row.papel)}</span>
                  </td>
                  <td className="tabular-nums">
                    {row.tensao_kv == null ? '—' : `${formatInteger(row.tensao_kv)} kV`}
                  </td>
                  <td className="break-words">
                    <Terminals from={row.subestacao_de} to={row.subestacao_para} />
                  </td>
                  <td data-align="right" className="tabular-nums">
                    {row.comprimento_km == null ? '—' : `${formatInteger(row.comprimento_km)} km`}
                  </td>
                  <td data-align="right" className="tabular-nums">
                    {row.capacidade_longa_mva == null ? (
                      <span className="text-warning">sem cadastro</span>
                    ) : (
                      `${formatInteger(row.capacidade_longa_mva)} MVA`
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {occurrences.maiores.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <h4 className="text-xs font-semibold text-(--sim-foreground)">
            Maiores ocorrências do período
          </h4>
          <ul className="flex flex-col gap-2">
            {occurrences.maiores.map((occurrence) => (
              <li
                key={occurrence.inicio}
                className="grid grid-cols-[5.5rem_minmax(0,1fr)_6.5rem] items-center gap-3 text-xs"
              >
                <span className="tabular-nums text-(--sim-foreground)">
                  {formatDate(occurrence.inicio)}
                </span>
                <div className="sim-bar h-2!" aria-hidden="true">
                  {/* Escala do desenho: a barra mais longa é a maior ocorrência. */}
                  <div
                    style={{ width: `${largest ? (occurrence.energia_mwh / largest) * 100 : 0}%` }}
                  />
                </div>
                <span className="text-right font-semibold tabular-nums text-(--sim-brand-ink)">
                  {formatNumber(occurrence.energia_mwh)} MWh
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="flex gap-2.5 rounded-lg bg-(--sim-background) px-3.5 py-3 text-xs leading-5 text-(--sim-foreground)">
        <Info className="mt-0.5 size-4 shrink-0 text-(--sim-muted-foreground)" aria-hidden="true" />
        <span>Capacidade é contexto: uma por equipamento, sem soma. {occurrences.aviso}</span>
      </p>
    </article>
  )
}
