import { Link, useParams } from 'react-router'
import { RestrictionDetailHeader } from '@/features/restrictions/components/restriction-detail-header'
import { RestrictionDetailMetrics } from '@/features/restrictions/components/restriction-detail-metrics'
import { RestrictionEquipment } from '@/features/restrictions/components/restriction-equipment'
import { RestrictionNotMeasured } from '@/features/restrictions/components/restriction-not-measured'
import { RestrictionHistoryChart } from '@/features/restrictions/components/restriction-history-chart'
import { RestrictionOccurrencesTable } from '@/features/restrictions/components/restriction-occurrences-table'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { restrictionName, useRestriction } from '@/features/restrictions/api/get-restriction'
import { Breadcrumbs } from '@/components/layout/breadcrumbs'

const source = 'eolica' as const

export default function RestrictionDetail() {
  const { id } = useParams()
  const query = useRestriction({ restrictionId: id ?? '', source })

  if (query.isPending) {
    return (
      <div className="mx-auto flex max-w-360 justify-center px-6 py-16">
        <Spinner />
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="mx-auto max-w-360 px-6 py-8">
        <p className="text-sm text-warning">
          Não foi possível carregar a restrição "{id}": {query.error.message}
        </p>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/">Voltar para Restrições</Link>
        </Button>
      </div>
    )
  }

  const item = query.data

  return (
    <div className="sim-page">
      <main className="mx-auto max-w-screen-2xl px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
        <Breadcrumbs
          className="mb-4"
          items={[{ label: 'Restrições', to: '/' }, { label: restrictionName(item) }]}
        />

        <section className="sim-card">
          <RestrictionDetailHeader item={item} />
          <RestrictionDetailMetrics item={item} />
        </section>

        <RestrictionNotMeasured item={item} className="mt-4" />
        <RestrictionEquipment item={item} />
        <RestrictionHistoryChart restrictionId={item.id} source={source} />
        <RestrictionOccurrencesTable restrictionId={item.id} source={source} />
      </main>
    </div>
  )
}
