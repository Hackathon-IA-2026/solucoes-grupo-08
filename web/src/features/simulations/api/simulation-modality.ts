import type { SchemaModalidade } from '@/api/gerado/tipos'

/** Os valores são os do contrato: na tela, `equipamento` é "Adição de circuito". */
export type SimulationModality = SchemaModalidade

export type ModalityOption = {
  id: SimulationModality
  title: string
  description: string
  caption: string
}

export const modalityOptions: ModalityOption[] = [
  {
    id: 'bateria',
    title: 'Bateria',
    description:
      'Absorve o corte e devolve depois. Presa a uma subestação da restrição, nunca a uma linha.',
    caption:
      'Cuidado declarado: devolve pela mesma linha, e a devolução pode esbarrar no mesmo limite. Isso não entra na conta.',
  },
  {
    id: 'equipamento',
    title: 'Adição de circuito',
    description:
      'Uma linha nova entre as mesmas subestações, ou por outro caminho. Cada linha da restrição pode receber a sua.',
    caption:
      'Única intervenção em linha que ataca limite de tensão: o circuito novo reduz a reatância do corredor e reparte o fluxo. Cabo mais grosso não resolve.',
  },
  {
    id: 'combinada',
    title: 'Bateria mais adição de circuito',
    description: 'As duas no mesmo histórico, com a ordem de aplicação exibida, não implícita.',
    caption:
      'Regra dura, em toda meia hora: recuperado combinado ≤ cortado. A mesma energia nunca é creditada duas vezes.',
  },
]
