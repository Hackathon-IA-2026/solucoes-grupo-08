import type { SchemaCenario, SchemaModalidade } from '@/api/gerado/tipos'

/** Na tela, `equipamento` é "Adição de circuito". */
export const modalityLabels: Record<SchemaModalidade, string> = {
  bateria: 'Bateria',
  equipamento: 'Adição de circuito',
  combinada: 'Bateria mais adição de circuito',
}

export const scenarioLabels: Record<SchemaCenario, string> = {
  conservador: 'Conservador',
  referencia: 'Referência',
  otimista: 'Otimista',
}
