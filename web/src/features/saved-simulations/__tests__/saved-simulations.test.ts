import { describe, expect, it } from 'vitest'
import { configurationFields } from '../api/configuration-fields'
import type { Configuration, FullRevision } from '../api/get-simulation'
import { premiseValue } from '../api/premise-value'
import { compareSections } from '../components/compare/compare-rows'

const financial: Configuration['financeira'] = {
  cenario: 'referencia',
  taxa_desconto_aa: 0.09,
  horizonte_anos: 25,
  capex_reais: 1_000_000,
  opex_fixo_reais_ano: 0,
  opex_variavel_reais_mwh: 0,
  valor_residual_reais: 0,
  receitas_adicionais_reais_ano: 0,
  reposicoes: [],
}

const battery: NonNullable<Configuration['bateria']> = {
  subestacao: 'SE-A',
  potencia_mw: 100,
  capacidade_mwh: 400,
  soc_inicial: 0,
  soc_min: 0,
  soc_max: 1,
  eficiencia_ida_volta: 0.85,
  disponibilidade: 1,
  degradacao_por_ciclo: 0,
  degradacao_por_ano: 0,
  vida_util_anos: 15,
}

const equipment: NonNullable<Configuration['equipamento']> = {
  tipo: 'adicao_circuito',
  cod_equipamento: 'LT-1',
  ganho_limite_mw: 40,
  disponibilidade: 1,
  vida_util_anos: 25,
}

const combinedForm: Configuration = {
  modalidade: 'combinada',
  bateria: battery,
  equipamento: equipment,
  financeira: financial,
}
const circuitOnly: Configuration = {
  modalidade: 'equipamento',
  bateria: null,
  equipamento: equipment,
  financeira: financial,
}

function revision(id: number, configuration: Configuration, npv: number): FullRevision {
  return {
    id,
    simulacao_id: id,
    nome: `Simulação ${id}`,
    pergunta: null,
    restricao_id: 'r1',
    snapshot_id: '2026-09-15',
    metodo_versao: '0.4.0',
    nota: null,
    procedencia: 'por_pessoa',
    cruzamentos: { payback_no_horizonte: null, tir_acima_da_taxa: null },
    revisao_anterior_id: null,
    criada_em: '2026-09-20T12:00:00Z',
    periodo_inicio: '2025-09-01T00:00:00',
    periodo_fim: '2026-09-01T00:00:00',
    configuracao: configuration,
    premissas_usadas: {},
    avisos: [],
    revisoes: [
      {
        id,
        posicao: 1,
        atual: true,
        criada_em: '2026-09-20T12:00:00Z',
        nota: null,
        procedencia: 'por_pessoa',
        revisao_anterior_id: null,
      },
    ],
    resultado: {
      metodo_versao: '0.4.0',
      snapshot_id: '2026-09-15',
      restricao_id: 'r1',
      premissas_usadas: {},
      avisos: [],
      tecnico: {
        cortado_mw: [],
        evitado_equipamento_mw: [],
        absorvido_bateria_mw: [],
        devolvido_bateria_mw: [],
        residual_mw: [],
        soc_mwh: [],
        energia_cortada_mwh: 1000,
        energia_evitada_equipamento_mwh: 300,
        energia_absorvida_bateria_mwh: 200,
        energia_devolvida_bateria_mwh: 150,
        energia_recuperada_mwh: 450,
        fracao_recuperada: 0.45,
      },
      financeiro: {
        vpl_reais: npv,
        tir_aa: null,
        payback_simples_anos: null,
        payback_descontado_anos: null,
        custo_por_mwh_reais: null,
        beneficio_bruto_reais: 0,
        beneficio_liquido_reais: 0,
        fluxos: [],
      },
    },
  }
}

describe('revision configuration', () => {
  it('only brings the block the modality has', () => {
    const fields = configurationFields(circuitOnly)
    expect(fields.find((field) => field.id === 'potencia')?.value).toBeNull()
    expect(fields.find((field) => field.id === 'ganho')?.value).toMatch(/MW$/)
  })

  it('shows fraction as percent and uses the line name when there is one', () => {
    const fields = configurationFields(combinedForm, 'LT 500 kV Teste')
    expect(fields.find((field) => field.id === 'eficiencia')?.value).toBe('85,0 %')
    expect(fields.find((field) => field.id === 'linha')?.value).toBe('LT 500 kV Teste')
  })

  it('omitted initial charge shows that the minimum charge applied, not zero', () => {
    const config: Configuration = {
      ...combinedForm,
      bateria: { ...battery, soc_inicial: null, soc_min: 0.2 },
    }
    const initial = configurationFields(config).find((field) => field.id === 'carga_inicial')
    expect(initial?.value).toBe('Assume a carga mínima (20,0 %)')
  })

  it('an informed initial charge appears as percent', () => {
    const config: Configuration = { ...combinedForm, bateria: { ...battery, soc_inicial: 0.5 } }
    const initial = configurationFields(config).find((field) => field.id === 'carga_inicial')
    expect(initial?.value).toBe('50,0 %')
  })
})

describe('comparator', () => {
  const sections = compareSections(
    { revision: revision(1, combinedForm, 500_000) },
    { revision: revision(2, circuitOnly, 250_000) },
  )
  const row = (title: string, label: string) =>
    sections.find((section) => section.title === title)?.rows.find((row) => row.label === label)

  it('says why the block is missing, instead of leaving it empty', () => {
    expect(row('Energia, 12 meses', 'Bateria absorveu')?.b).toEqual({ missing: 'sem bateria' })
    expect(row('Configuração', 'Potência da bateria')?.b).toEqual({ missing: 'sem bateria' })
  })

  it("brings the API's ready numbers, without recalculating", () => {
    const npv = row('Financeiro', 'VPL')
    expect(npv?.a).toHaveProperty('text')
    expect(npv?.a).not.toEqual(npv?.b)
  })

  it('a null value from the API becomes a dash, not zero', () => {
    expect(row('Financeiro', 'TIR')?.a).toEqual({ missing: '—' })
  })
})

describe('premises', () => {
  it('formats number, text and boolean in pt-BR', () => {
    expect(premiseValue(250)).toBe('250')
    expect(premiseValue(0.09)).toBe('0,0900')
    expect(premiseValue(true)).toBe('sim')
    expect(premiseValue('vinculo')).toBe('vinculo')
  })
})
