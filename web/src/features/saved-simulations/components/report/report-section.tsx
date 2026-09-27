import type { ReactNode } from 'react'
import { cn } from '@/utils/cn'

/** Unidade ao lado do número, mais apagada. */
export function Unit({ children }: { children: ReactNode }) {
  return <span className="text-xs text-text-muted">{children}</span>
}

// Número com unidade ou moeda, no formato em que o analista escreve e o verificador confere:
// "R$ -71,5 milhões", "21.500 MWh", "6,4 %", "8,4 anos", "8 % a.a.".
// Ponto só como separador de milhar, para o ponto final da frase não entrar no destaque.
const NUMBER_IN_PROSE =
  /(R\$\s?-?\d+(?:\.\d{3})*(?:,\d+)?(?:\s(?:milhões|mil))?|-?\d+(?:\.\d{3})*(?:,\d+)?\s?(?:% a\.a\.|%|MWh|MW|anos))/g

/**
 * Prosa do modelo com os números destacados. Destacar não é calcular: o texto vem pronto da API
 * e o verificador já conferiu cada número contra a parte calculada antes de gravar.
 */
export function ProseText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(NUMBER_IN_PROSE)

  return (
    <p className={cn('text-sm leading-6 text-(--sim-foreground)', className)}>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <span
            key={index}
            className="whitespace-nowrap border-b border-dotted border-(--sim-brand) text-(--sim-brand) tabular-nums"
          >
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </p>
  )
}

/** Título de seção do relatório: rótulo em maiúsculas pequenas, com algo opcional à direita. */
export function SectionHeading({
  id,
  title,
  aside,
}: {
  id: string
  title: ReactNode
  aside?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <h2 id={id} className="sim-eyebrow text-(--sim-muted-foreground)">
        {title}
      </h2>
      {aside}
    </div>
  )
}
