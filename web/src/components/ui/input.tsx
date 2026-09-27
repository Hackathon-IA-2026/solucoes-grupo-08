import { X } from 'lucide-react'
import type { InputHTMLAttributes, ReactNode, Ref } from 'react'
import { cn } from '@/utils/cn'

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  ref?: Ref<HTMLInputElement>
  adornment?: ReactNode
  /** Unidade ou faixa, à direita do valor: MW, R$ por ano, 0 a 1. */
  unit?: ReactNode
  onClear?: () => void
  containerClassName?: string
}

function Input({
  className,
  containerClassName,
  type,
  ref,
  adornment,
  unit,
  onClear,
  value,
  disabled,
  ...props
}: InputProps) {
  return (
    <div
      className={cn(
        'flex h-9 w-full items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-text-primary transition-colors',
        'focus-within:ring-2 focus-within:ring-focus',
        disabled && 'cursor-not-allowed opacity-50',
        containerClassName,
      )}
    >
      {adornment && (
        <span className="shrink-0 whitespace-nowrap text-text-muted" aria-hidden="true">
          {adornment}
        </span>
      )}
      <input
        type={type}
        ref={ref}
        value={value}
        disabled={disabled}
        className={cn(
          'min-w-0 flex-1 bg-transparent py-1 text-text-primary placeholder:text-text-muted focus:outline-none disabled:cursor-not-allowed',
          className,
        )}
        {...props}
      />
      {unit && <span className="shrink-0 whitespace-nowrap text-sm text-text-muted">{unit}</span>}
      {onClear && typeof value === 'string' && value.length > 0 && (
        <button
          type="button"
          onClick={onClear}
          className="shrink-0 rounded-sm text-text-muted transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          aria-label="Limpar"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

export { Input }
