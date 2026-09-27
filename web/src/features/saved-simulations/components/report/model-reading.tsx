import { Check } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Derived, ProseSection, Report } from '../../api/report'
import { fieldValues, readReais, SUSPICIOUS_CAPEX_REAIS } from './report-format'
import { ProseText, SectionHeading } from './report-section'
import { cn } from '@/utils/cn'

const proseSectionLabels: Record<ProseSection, string> = {
  leitura_geral: 'Leitura geral',
  o_que_variou: 'O que variou e o efeito',
  sensibilidade: 'Sensibilidade',
  fora_do_metodo: 'O que está fora do método',
  perguntas_que_ficaram: 'Perguntas que ficaram',
}

const failureReasons = {
  sem_origem: 'número sem origem na parte calculada',
  forma_proibida: 'forma proibida',
  tamanho: 'passou do tamanho da seção',
} as const

const PROSE = 'max-w-[72ch] text-[0.9375rem] leading-7'

function ProseCard({ section, children }: { section: ProseSection; children: ReactNode }) {
  return (
    <article className="sim-panel flex flex-col gap-3 p-6! lg:p-7!">
      <h3 className="sim-display text-base font-semibold text-(--sim-brand-ink)">
        {proseSectionLabels[section]}
      </h3>
      {children}
    </article>
  )
}

// Os campos e premissas que decidem a leitura financeira, na ordem em que se lê o VPL.
const KEY_FIELDS: { campo: string; label: string }[] = [
  { campo: 'financeira.preco_energia_reais_mwh', label: 'Preço da energia' },
  { campo: 'financeira.taxa_desconto_aa', label: 'Taxa de desconto' },
  { campo: 'financeira.horizonte_anos', label: 'Horizonte' },
  { campo: 'financeira.cenario', label: 'Cenário' },
  { campo: 'financeira.capex_reais', label: 'Investimento inicial' },
]
const KEY_PREMISES: { id: string; label: string }[] = [
  { id: 'preco_energia', label: 'Preço da energia padrão' },
  { id: 'despacho_bateria', label: 'Modo de despacho' },
  { id: 'bateria_carrega_so_do_corte', label: 'Bateria carrega só do corte' },
]

function KeyAssumptions({ derived }: { derived: Derived }) {
  const fields = KEY_FIELDS.flatMap(({ campo, label }) => {
    const values = fieldValues(derived, campo)
    if (values.length === 0) return []
    const suspicious =
      campo === 'financeira.capex_reais' &&
      values.some((value) => (readReais(value) ?? Infinity) < SUSPICIOUS_CAPEX_REAIS)
    return [{ key: campo, label, value: values.join(' · '), suspicious }]
  })
  const premises = KEY_PREMISES.flatMap(({ id, label }) => {
    const premise = derived.premissas_expostas.find((item) => item.id === id)
    if (!premise) return []
    const value = `${premise.valor}${premise.unidade ? ` ${premise.unidade}` : ''}`
    return [{ key: id, label, value, suspicious: false }]
  })
  const rows = [...fields, ...premises]
  if (rows.length === 0) return null

  return (
    <aside aria-labelledby="premissas-chave" className="sim-panel flex flex-col gap-1 p-6!">
      <h3
        id="premissas-chave"
        className="sim-display mb-2 text-base font-semibold text-(--sim-brand-ink)"
      >
        Premissas-chave
      </h3>
      <dl className="flex flex-col divide-y divide-(--sim-border) text-sm">
        {rows.map((row) => (
          <div key={row.key} className="flex justify-between gap-4 py-3">
            <dt className="text-(--sim-muted-foreground)">{row.label}</dt>
            <dd
              className={cn(
                'text-right font-semibold tabular-nums text-(--sim-brand-ink)',
                row.suspicious && 'text-(--sim-alert)',
                row.value === 'vazio' && 'font-normal text-(--sim-muted-foreground)',
              )}
            >
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}

/** A prosa do modelo, com o selo da verificação, e as premissas que decidem o resultado. */
export function ModelReading({ report }: { report: Report }) {
  const { prosa: prose, verificacao: verification, estado: state, derivados: derived } = report
  const passed = verification.resultado === 'passou'

  const heading = (
    <SectionHeading
      id="leitura"
      title="Leitura do modelo"
      aside={
        passed && (
          <p className="flex flex-wrap items-center gap-2 text-xs text-(--sim-foreground)">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-success-light px-2.5 py-0.5 font-semibold text-success">
              <Check className="size-3.5" aria-hidden="true" />
              Verificado
            </span>
          </p>
        )
      }
    />
  )

  if (state === 'falhou') {
    return (
      <section aria-labelledby="leitura" className="flex flex-col gap-3">
        {heading}
        <p role="alert" className="sim-panel text-sm text-danger">
          A geração falhou{report.erro ? `: ${report.erro}` : '.'} Nada foi gravado como pronto.
        </p>
      </section>
    )
  }

  // Barrado: a prosa fica retida no servidor e nunca chega como prosa. Só as falhas aparecem.
  if (state === 'barrado' || !prose) {
    const failures = verification.falhas ?? []
    return (
      <section aria-labelledby="leitura" className="flex flex-col gap-3">
        {heading}
        <div role="alert" className="sim-panel border border-danger">
          <p className="text-sm font-semibold text-danger">Prosa barrada pela verificação</p>
          <p className="mt-1 text-sm text-(--sim-muted-foreground)">
            A prosa não é exibida: pelo menos um número ou uma forma não passou na conferência
            contra a parte calculada. As tabelas abaixo são código e continuam valendo.
          </p>
          {failures.length > 0 && (
            <ul className="mt-3 flex flex-col gap-2">
              {failures.map((failure, index) => (
                <li key={index} className="text-sm">
                  <span className="font-semibold text-(--sim-brand-ink)">
                    {proseSectionLabels[failure.secao]}
                  </span>
                  <span className="text-(--sim-muted-foreground)">
                    {' '}
                    · {failureReasons[failure.motivo]}
                  </span>
                  {failure.numero && (
                    <span className="text-danger tabular-nums"> · {failure.numero}</span>
                  )}
                  <span className="mt-0.5 block italic text-(--sim-muted-foreground)">
                    “{failure.trecho}”
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="leitura" className="flex flex-col gap-3">
      {heading}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-4">
          <ProseCard section="leitura_geral">
            <ProseText text={prose.leitura_geral} className={PROSE} />
          </ProseCard>
          <ProseCard section="sensibilidade">
            <ProseText text={prose.sensibilidade} className={PROSE} />
          </ProseCard>
          {prose.o_que_variou.length > 0 && (
            <ProseCard section="o_que_variou">
              <ul className="flex list-disc flex-col gap-2 pl-4 marker:text-(--sim-muted-foreground)">
                {prose.o_que_variou.map((sentence, index) => (
                  <li key={index}>
                    <ProseText text={sentence} className={PROSE} />
                  </li>
                ))}
              </ul>
            </ProseCard>
          )}
          <ProseCard section="fora_do_metodo">
            <ProseText text={prose.fora_do_metodo} className={PROSE} />
          </ProseCard>
        </div>
        {derived && <KeyAssumptions derived={derived} />}
      </div>
    </section>
  )
}
