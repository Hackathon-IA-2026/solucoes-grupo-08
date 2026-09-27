import { describe, expect, it } from 'vitest'
import { formDataFromRevision } from '../from-revision'
import { initialValues } from '../schema'
import type { Configuration, FullRevision } from '@/features/saved-simulations/api/get-simulation'

const financial: Configuration['financeira'] = {
  cenario: 'referencia',
  taxa_desconto_aa: 0.09,
  horizonte_anos: 25,
  capex_reais: 1_000_000,
  opex_fixo_reais_ano: 0,
  opex_variavel_reais_mwh: 0,
  valor_residual_reais: 0,
  receitas_adicionais_reais_ano: 0,
  reposicoes: [{ ano: 10, valor_reais: 50_000 }],
}

const battery: NonNullable<Configuration['bateria']> = {
  subestacao: 'SE-A',
  potencia_mw: 100,
  capacidade_mwh: 400,
  soc_inicial: null,
  soc_min: 0.2,
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
  capacidade_depois_mva: null,
  disponibilidade: 1,
  vida_util_anos: 25,
}

/** Uma revisão salva mínima, só com o que `formDataFromRevision` lê. */
function revision(overrides: Partial<FullRevision> = {}): FullRevision {
  return {
    id: 20,
    simulacao_id: 7,
    nome: 'Bateria 100 MW',
    pergunta: null,
    restricao_id: 'r1',
    snapshot_id: '2026-09-15',
    metodo_versao: '0.5.1',
    revisao_anterior_id: null,
    criada_em: '2026-09-20T12:00:00Z',
    nota: null,
    procedencia: 'por_pessoa',
    cruzamentos: { payback_no_horizonte: null, tir_acima_da_taxa: null },
    periodo_inicio: '2025-09-01T00:00:00',
    periodo_fim: '2026-09-01T00:00:00',
    configuracao: {
      modalidade: 'combinada',
      bateria: battery,
      equipamento: equipment,
      financeira: financial,
    },
    premissas_usadas: {},
    avisos: [],
    revisoes: [
      {
        id: 20,
        posicao: 1,
        atual: true,
        criada_em: '2026-09-20T12:00:00Z',
        nota: null,
        procedencia: 'por_pessoa',
        revisao_anterior_id: null,
      },
    ],
    resultado: {
      metodo_versao: '0.5.1',
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
        energia_cortada_mwh: 0,
        energia_evitada_equipamento_mwh: 0,
        energia_absorvida_bateria_mwh: 0,
        energia_devolvida_bateria_mwh: 0,
        energia_recuperada_mwh: 0,
        fracao_recuperada: 0,
      },
      financeiro: {
        vpl_reais: 0,
        tir_aa: null,
        payback_simples_anos: null,
        payback_descontado_anos: null,
        custo_por_mwh_reais: null,
        beneficio_bruto_reais: 0,
        beneficio_liquido_reais: 0,
        fluxos: [],
      },
    },
    ...overrides,
  }
}

describe('formDataFromRevision', () => {
  it('brings name, question and the whole configuration into the form', () => {
    const data = formDataFromRevision(revision({ pergunta: 'E se a bateria fosse maior?' }))

    expect(data.step1).toEqual({ nome: 'Bateria 100 MW', pergunta: 'E se a bateria fosse maior?' })
    expect(data.step3.modalidade).toBe('combinada')
    expect(data.step4.bateria).toEqual(battery)
    expect(data.step4.equipamento).toEqual(equipment)
    expect(data.step5.reposicoes).toEqual([{ ano: 10, valor_reais: 50_000 }])
  })

  it('a null question becomes empty text, never the word null', () => {
    expect(formDataFromRevision(revision({ pergunta: null })).step1.pergunta).toBe('')
  })

  it("the block the revision's modality didn't have goes back to the form's blank state", () => {
    const batteryOnly = revision({
      configuracao: {
        modalidade: 'bateria',
        bateria: battery,
        equipamento: null,
        financeira: financial,
      },
    })
    expect(formDataFromRevision(batteryOnly).step4.equipamento).toEqual(
      initialValues.step4.equipamento,
    )

    const circuitOnly = revision({
      configuracao: {
        modalidade: 'equipamento',
        bateria: null,
        equipamento: equipment,
        financeira: financial,
      },
    })
    expect(formDataFromRevision(circuitOnly).step4.bateria).toEqual(initialValues.step4.bateria)
  })

  it('initial charge the revision assumed (null) stays null, it does not become the minimum charge', () => {
    const data = formDataFromRevision(revision())
    expect(data.step4.bateria.soc_inicial).toBeNull()
  })

  it('correcao_minutos comes from premissas_usadas; without it, assumes on', () => {
    const ligada = revision({
      premissas_usadas: {
        correcao_minutos: {
          id: 'correcao_minutos',
          descricao: '',
          fonte: '',
          valor: false,
          status: 'nao_verificada',
        },
      },
    })
    expect(formDataFromRevision(ligada).step2.correcao_minutos).toBe(false)
    expect(formDataFromRevision(revision()).step2.correcao_minutos).toBe(true)
  })

  it('fonte comes from premissas_usadas.fonte_geracao (feature 15)', () => {
    const bothSources = revision({
      premissas_usadas: {
        fonte_geracao: {
          id: 'fonte_geracao',
          descricao: '',
          fonte: '',
          valor: 'ambas',
          status: 'proposta',
        },
      },
    })
    expect(formDataFromRevision(bothSources).step2.fonte).toBe('ambas')
  })

  it('without a generation source (revision from before feature 15), assumes wind', () => {
    expect(formDataFromRevision(revision()).step2.fonte).toBe('eolica')
  })

  it('an unexpected generation source falls back to wind, never crashes', () => {
    const strange = revision({
      premissas_usadas: {
        fonte_geracao: {
          id: 'fonte_geracao',
          descricao: '',
          fonte: '',
          valor: 'nuclear',
          status: 'proposta',
        },
      },
    })
    expect(formDataFromRevision(strange).step2.fonte).toBe('eolica')
  })
})
