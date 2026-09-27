import { describe, expect, it } from 'vitest'
import { buildRequest } from '../build-request'
import { initialValues, type SimulationFormData } from '../schema'

/** Um formulário completo na modalidade combinada, que cada teste ajusta. */
function combinedForm(): SimulationFormData {
  return structuredClone({
    step1: { nome: '  Reforço com bateria  ', pergunta: '' },
    step2: { fonte: 'eolica', correcao_minutos: true },
    step3: { modalidade: 'combinada' },
    step4: {
      bateria: {
        ...initialValues.step4.bateria,
        subestacao: 'ALFA',
        potencia_mw: 100.5,
        capacidade_mwh: 400,
        eficiencia_ida_volta: 0.85,
      },
      equipamento: {
        ...initialValues.step4.equipamento,
        cod_equipamento: 'FICT-A1',
        ganho_limite_mw: 40,
      },
    },
    step5: {
      ...initialValues.step5,
      taxa_desconto_aa: 0.09,
      horizonte_anos: 30,
      capex_reais: 1500000,
      reposicoes: [{ ano: 15, valor_reais: 200000 }],
    },
  })
}

const create = { mode: 'create', restrictionId: 'R1' } as const

describe('buildRequest', () => {
  it('keeps the numbers as they are and trims the name', () => {
    const request = buildRequest(create, combinedForm())

    expect(request.restricao_id).toBe('R1')
    expect(request.nome).toBe('Reforço com bateria')
    expect(request.configuracao.bateria?.potencia_mw).toBe(100.5)
    expect(request.configuracao.bateria?.eficiencia_ida_volta).toBe(0.85)
    expect(request.configuracao.financeira.horizonte_anos).toBe(30)
    expect(request.configuracao.financeira.reposicoes).toEqual([{ ano: 15, valor_reais: 200000 }])
  })

  it('empty optional field is left out of the request, so the API applies the default', () => {
    // O formulário nasce com o padrão do tipo; aqui os campos são esvaziados de propósito.
    const data = combinedForm()
    data.step4.bateria.soc_min = null
    data.step4.bateria.vida_util_anos = null
    data.step5.opex_fixo_reais_ano = null
    const {
      bateria: battery,
      equipamento: equipment,
      financeira: financial,
    } = buildRequest(create, data).configuracao

    expect(battery?.soc_min).toBeUndefined()
    expect(battery?.vida_util_anos).toBeUndefined()
    expect(equipment?.capacidade_depois_mva).toBeUndefined()
    expect(financial.opex_fixo_reais_ano).toBeUndefined()
    // Zero digitado é valor, e não ausência.
    data.step5.opex_fixo_reais_ano = 0
    expect(buildRequest(create, data).configuracao.financeira.opex_fixo_reais_ano).toBe(0)
  })

  it('empty question goes as null, and a filled one goes as is', () => {
    expect(buildRequest(create, combinedForm()).pergunta).toBeNull()
    const data = combinedForm()
    data.step1.pergunta = 'E se houvesse bateria?'
    expect(buildRequest(create, data).pergunta).toBe('E se houvesse bateria?')
  })

  it('the circuit is always `adicao_circuito`', () => {
    expect(buildRequest(create, combinedForm()).configuracao.equipamento?.tipo).toBe(
      'adicao_circuito',
    )
  })

  it("does not send the block the modality doesn't accept", () => {
    const data = combinedForm()
    data.step3.modalidade = 'bateria'
    const batteryOnly = buildRequest(create, data).configuracao
    expect(batteryOnly.bateria).toBeDefined()
    expect(batteryOnly.equipamento).toBeUndefined()

    data.step3.modalidade = 'equipamento'
    const circuitOnly = buildRequest(create, data).configuracao
    expect(circuitOnly.bateria).toBeUndefined()
    expect(circuitOnly.equipamento).toBeDefined()
  })
})

describe('revising an existing simulation', () => {
  const revise = { mode: 'revise', simulationId: 7 } as const

  it('sends simulacao_id, and never restricao_id', () => {
    const request = buildRequest(revise, combinedForm())

    expect(request.simulacao_id).toBe(7)
    expect(request.restricao_id).toBeUndefined()
  })

  it('create still has no simulacao_id', () => {
    expect(buildRequest(create, combinedForm()).simulacao_id).toBeUndefined()
  })
})
