import { TriangleAlert } from 'lucide-react'
import { isRouteErrorResponse, Link, useRouteError } from 'react-router'
import { NotFound } from './not-found'
import { Button } from '@/components/ui/button'

/** Erro de rota, no lugar do padrão do React Router. Renderiza dentro do layout do produto. */
export function RouteError() {
  const error = useRouteError()

  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />

  return (
    <div
      role="alert"
      className="mx-auto flex max-w-360 flex-col items-center px-6 py-24 text-center"
    >
      <TriangleAlert className="h-10 w-10 text-warning" aria-hidden="true" />
      <h1 className="mt-4 text-2xl font-semibold text-text-primary">Algo deu errado</h1>
      <p className="mt-2 max-w-md text-sm text-text-secondary">
        {error instanceof Error ? error.message : 'Ocorreu um erro inesperado nesta página.'}
      </p>
      <Button asChild className="mt-6">
        <Link to="/">Voltar para o início</Link>
      </Button>
    </div>
  )
}
