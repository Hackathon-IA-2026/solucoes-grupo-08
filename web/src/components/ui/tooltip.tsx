import { Info } from 'lucide-react'
import * as Primitive from '@radix-ui/react-tooltip'
import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/utils/cn'

/** Uma única vez, na raiz do app: controla o atraso antes do tooltip aparecer. */
export const TooltipProvider = Primitive.Provider
export const Tooltip = Primitive.Root
export const TooltipTrigger = Primitive.Trigger

export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentProps<typeof Primitive.Content>) {
  return (
    <Primitive.Portal>
      <Primitive.Content
        sideOffset={sideOffset}
        className={cn(
          'z-50 max-w-70 text-balance rounded-md border border-border bg-surface px-2.5 py-1.5',
          'text-xs text-text-primary shadow-md',
          className,
        )}
        {...props}
      />
    </Primitive.Portal>
  )
}

type InfoTooltipProps = {
  /** O que o ícone explica, para quem usa leitor de tela: "Ajuda: Energia cortada". */
  label: string
  children: ReactNode
}

/**
 * O gatilho padrão para sigla ou jargão: ícone `Info` que abre o tooltip no hover, no foco por
 * teclado e no toque — um `<button>`, nunca um `<span>`, porque só elemento focável abre por
 * teclado.
 */
export function InfoTooltip({ label, children }: InfoTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          className="inline-flex shrink-0 rounded-sm text-text-muted transition-colors hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <Info className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent>{children}</TooltipContent>
    </Tooltip>
  )
}

type HeaderTooltipProps = {
  /** O texto do cabeçalho, que também é o gatilho — sublinhado pontilhado, como a spec pede. */
  label: string
  children: ReactNode
}

/** Gatilho para cabeçalho de tabela: o próprio texto, sublinhado pontilhado, é o gatilho. */
export function HeaderTooltip({ label, children }: HeaderTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-default underline decoration-dotted underline-offset-4">
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent>{children}</TooltipContent>
    </Tooltip>
  )
}
