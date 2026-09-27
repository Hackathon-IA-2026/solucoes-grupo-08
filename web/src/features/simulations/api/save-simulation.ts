import { useMutation, useQueryClient } from '@tanstack/react-query'
import { httpClient } from '@/api/client'
import type { SchemaPedidoDeSalvamento, SchemaRevisaoSalva } from '@/api/gerado/tipos'
import type { MutationConfig } from '@/lib/react-query'

export type SavedRevision = SchemaRevisaoSalva

type ContractConfiguration = SchemaPedidoDeSalvamento['configuracao']
type Battery = NonNullable<ContractConfiguration['bateria']>
type Equipment = NonNullable<ContractConfiguration['equipamento']>
type Financial = ContractConfiguration['financeira']

/**
 * O corpo de `POST /simulacoes`. O cliente gerado marca como obrigatório todo campo que tem
 * `default`, porque o mesmo schema descreve a resposta, que sempre vem completa. No pedido esses
 * campos são opcionais: omitidos, a API aplica o padrão do tipo. Aqui só ficam obrigatórios os que
 * o contrato exige de quem envia.
 */
export type SaveRequest = Omit<SchemaPedidoDeSalvamento, 'configuracao'> & {
  configuracao: Omit<ContractConfiguration, 'bateria' | 'equipamento' | 'financeira'> & {
    bateria?: Partial<Battery> & Pick<Battery, 'subestacao' | 'potencia_mw' | 'capacidade_mwh'>
    equipamento?: Partial<Equipment> &
      Pick<Equipment, 'tipo' | 'cod_equipamento' | 'ganho_limite_mw'>
    financeira: Partial<Financial> &
      Pick<Financial, 'cenario' | 'taxa_desconto_aa' | 'horizonte_anos' | 'capex_reais'>
  }
}

/** Calcula e salva como revisão. Alterar depois cria revisão nova; nada se sobrescreve. */
export const saveSimulation = (request: SaveRequest): Promise<SavedRevision> => {
  return httpClient.post('/simulacoes', request)
}

type UseSaveSimulationOptions = {
  mutationConfig?: MutationConfig<typeof saveSimulation>
}

export const useSaveSimulation = ({ mutationConfig }: UseSaveSimulationOptions = {}) => {
  const queryClient = useQueryClient()
  const { onSuccess, ...rest } = mutationConfig ?? {}

  return useMutation({
    // A lista de simulações e as revisões irmãs mudaram: a próxima leitura vem da API.
    onSuccess: (...args) => {
      void queryClient.invalidateQueries({ queryKey: ['simulacoes'] })
      onSuccess?.(...args)
    },
    ...rest,
    mutationFn: saveSimulation,
  })
}
