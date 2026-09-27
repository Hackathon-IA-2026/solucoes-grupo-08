import { useSimulations } from './get-simulations'
import type { Crumb } from '@/components/layout/breadcrumbs'

/**
 * O nível da simulação na trilha das telas que só conhecem o id dela (relatórios, explorações):
 * o nome, levando à revisão atual. Vem da lista de simulações, que costuma estar no cache.
 * Enquanto não chega, o nível aparece pelo id e sem link.
 */
export function useSimulationCrumb(simulationId: number, revisionId?: number): Crumb {
  const simulation = useSimulations().data?.find((item) => item.id === simulationId)
  if (!simulation) return { label: `Simulação ${simulationId}` }
  const current =
    simulation.revisoes.find((revision) => revision.atual) ?? simulation.revisoes.at(0)
  const target = revisionId ?? current?.id
  return { label: simulation.nome, to: target != null ? `/simulacoes/${target}` : undefined }
}
