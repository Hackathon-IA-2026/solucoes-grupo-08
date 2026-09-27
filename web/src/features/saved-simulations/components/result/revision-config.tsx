import { configurationFields } from '../../api/configuration-fields'
import type { Configuration } from '../../api/get-simulation'

type RevisionConfigProps = {
  configuration: Configuration
  /** Nome da linha do cadastro, quando conhecido. */
  lineName?: string
  position: number
}

/** A configuração que gerou o número, um campo por linha. O bloco ausente nem aparece. */
export function RevisionConfig({ configuration, lineName, position }: RevisionConfigProps) {
  const fields = configurationFields(configuration, lineName).filter(
    (field) => field.value !== null,
  )

  return (
    <section className="sim-panel">
      <div className="flex items-center gap-3">
        <h2 className="sim-panel-title">Configuração desta revisão</h2>
        <span className="text-xs text-(--sim-muted-foreground)">rev {position}</span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
        {fields.map((field) => (
          <div key={field.id} className="min-w-0">
            <dt className="text-xs text-(--sim-muted-foreground)">{field.label}</dt>
            <dd className="mt-0.5 text-xs font-bold text-(--sim-brand-ink)">{field.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
