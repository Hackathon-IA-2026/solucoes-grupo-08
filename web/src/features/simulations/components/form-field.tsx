import type { ReactNode } from 'react'
import { Controller, useFormContext } from 'react-hook-form'
import type { FormFieldPath } from '../form/constants'
import type { SimulationFormData } from '../form/schema'
import { InfoTooltip } from '@/components/ui/tooltip'
import { NumberInput, type NumberKind } from '@/components/ui/number-input'
import { cn } from '@/utils/cn'

type FieldLabelProps = {
  htmlFor?: string
  required?: boolean
  /** Status ou aviso ao lado do rótulo, como "não verificada". */
  badge?: ReactNode
  /** Explica sigla ou jargão do rótulo. Sem ele, nenhum ícone de ajuda aparece. */
  tooltip?: string
  children: ReactNode
}

/** Rótulo de campo. Sem `htmlFor`, vira um título de bloco (valor somente leitura). */
export function FieldLabel({ htmlFor, required, badge, tooltip, children }: FieldLabelProps) {
  const className = 'mb-1 flex items-center gap-2 text-sm font-medium text-text-secondary'
  const content = (
    <>
      {children}
      {tooltip && <InfoTooltip label={`Ajuda: ${children}`}>{tooltip}</InfoTooltip>}
      {required && <span className="font-semibold text-warning">obrigatório</span>}
      {badge}
    </>
  )
  return htmlFor ? (
    <label htmlFor={htmlFor} className={className}>
      {content}
    </label>
  ) : (
    <span className={className}>{content}</span>
  )
}

const idOf = (name: FormFieldPath) => name.replaceAll('.', '-')
const errorIdOf = (name: FormFieldPath) => `erro-${idOf(name)}`

/** A mensagem de erro do campo, logo abaixo dele. Some quando o campo está válido. */
export function FieldError({ name }: { name: FormFieldPath }) {
  const { getFieldState, formState } = useFormContext<SimulationFormData>()
  const message = getFieldState(name, formState).error?.message

  return message ? (
    <p id={errorIdOf(name)} role="alert" className="mt-1 text-sm text-danger">
      {message}
    </p>
  ) : null
}

type NumericFieldProps = {
  name: FormFieldPath
  label: string
  /** Unidade ou faixa, à direita do valor. */
  unit: string
  /** Texto do campo vazio. Sem ele, o obrigatório fica sem texto e o opcional diz "Padrão do tipo". */
  placeholder?: string
  /** `integer`: só dígitos. `decimal` (padrão): vírgula decimal. `money`: máscara de dinheiro. */
  kind?: NumberKind
  required?: boolean
  badge?: ReactNode
  tooltip?: string
  help?: ReactNode
}

/**
 * Campo numérico de `Configuracao`, ligado ao formulário. O valor no formulário é `number | null`.
 * Vazio e opcional é válido: vale o valor inicial do cenário ou o padrão do tipo, e a API decide.
 */
export function NumericField({
  name,
  label,
  unit,
  kind = 'decimal',
  placeholder,
  required,
  badge,
  tooltip,
  help,
}: NumericFieldProps) {
  const { control, getFieldState, formState } = useFormContext<SimulationFormData>()
  const id = `campo-${idOf(name)}`
  const invalid = Boolean(getFieldState(name, formState).error)

  return (
    <div>
      <FieldLabel htmlFor={id} required={required} badge={badge} tooltip={tooltip}>
        {label}
      </FieldLabel>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <NumberInput
            id={id}
            name={field.name}
            ref={field.ref}
            // Todo caminho numérico do formulário guarda `number | null`; o tipo de `name` é a união.
            value={field.value as number | null}
            onValueChange={field.onChange}
            onBlur={field.onBlur}
            kind={kind}
            placeholder={placeholder ?? (required ? undefined : 'Padrão do tipo')}
            unit={unit}
            aria-invalid={invalid}
            aria-describedby={invalid ? errorIdOf(name) : undefined}
            containerClassName={cn(invalid && 'border-danger')}
          />
        )}
      />
      <FieldError name={name} />
      {help && <p className="mt-1 text-sm text-text-muted">{help}</p>}
    </div>
  )
}

type ReadOnlyFieldProps = {
  label: string
  badge?: ReactNode
  tooltip?: string
  help?: ReactNode
  children: ReactNode
  warn?: boolean
}

/** Valor que a tela mostra mas o usuário não edita: capacidade do cadastro, preço da premissa. */
export function ReadOnlyField({ label, badge, tooltip, help, children, warn }: ReadOnlyFieldProps) {
  return (
    <div>
      <FieldLabel badge={badge} tooltip={tooltip}>
        {label}
      </FieldLabel>
      <div
        className={`flex h-9 items-center rounded-md border border-border bg-surface-secondary px-3 text-sm ${warn ? 'text-warning' : 'text-text-primary'}`}
      >
        {children}
      </div>
      {help && <p className="mt-1 text-sm text-text-muted">{help}</p>}
    </div>
  )
}
