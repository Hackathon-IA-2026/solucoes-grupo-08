import { lazy } from 'react'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { NotFound } from '@/components/errors/not-found'
import { RouteError } from '@/components/errors/route-error'
import Layout from './routes/layout'

const Restrictions = lazy(() => import('./routes/restrictions'))
const RestrictionDetail = lazy(() => import('./routes/restriction-detail'))
const SimulationNew = lazy(() => import('./routes/simulation-new'))
const Simulations = lazy(() => import('./routes/simulations'))
const SimulationResult = lazy(() => import('./routes/simulation-result'))
const SimulationReport = lazy(() => import('./routes/simulation-report'))
const SimulationReports = lazy(() => import('./routes/simulation-reports'))
const SimulationCompare = lazy(() => import('./routes/simulation-compare'))
const SimulationExploration = lazy(() => import('./routes/simulation-exploration'))
const SimulationExplorations = lazy(() => import('./routes/simulation-explorations'))

const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      {
        // Sem caminho: o erro aparece dentro do layout, com o cabeçalho, e não no lugar dele.
        ErrorBoundary: RouteError,
        children: [
          { index: true, Component: Restrictions },
          { path: 'restricoes/:id', Component: RestrictionDetail },
          { path: 'restricoes/:id/nova-simulacao', Component: SimulationNew },
          { path: 'simulacoes', Component: Simulations },
          { path: 'simulacoes/:revisaoId', Component: SimulationResult },
          { path: 'simulacoes/:simulacaoId/relatorios', Component: SimulationReports },
          {
            path: 'simulacoes/:simulacaoId/relatorios/:relatorioId',
            Component: SimulationReport,
          },
          { path: 'comparar', Component: SimulationCompare },
          { path: 'simulacoes/:simulacaoId/exploracoes', Component: SimulationExplorations },
          {
            path: 'simulacoes/:simulacaoId/exploracoes/:tarefaId',
            Component: SimulationExploration,
          },
          { path: '*', Component: NotFound },
        ],
      },
    ],
  },
])

export const AppRouter = () => <RouterProvider router={router} />
