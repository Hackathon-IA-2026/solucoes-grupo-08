import { describe, expect, it } from 'vitest'
import { visibleFields, stepFields, fieldForPremise, STEPS } from '../constants'
import { dataForModality, formSchema, initialValues, type SimulationFormData } from '../schema'

/** Um formulário válido para a modalidade combinada, que cada teste estraga do seu jeito. */
function validForm(): SimulationFormData {
  return structuredClone({
    ...initialValues,
    step1: { nome: 'Simulação de teste', pergunta: '' },
    step4: {
      bateria: {
        ...initialValues.step4.bateria,
        subestacao: 'ALFA',
        potencia_mw: 100,
        capacidade_mwh: 400,
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
    },
  })
}

/** Os caminhos com erro, como o React Hook Form os nomeia: `step4.bateria.potencia_mw`. */
function pathsWithError(data: SimulationFormData) {
  const result = formSchema.safeParse(data)
  return result.success ? [] : result.error.issues.map((error) => error.path.join('.'))
}

describe('form schema', () => {
  it('accepts a complete form', () => {
    expect(pathsWithError(validForm())).toEqual([])
  })

  it('the empty form only fails where something is required', () => {
    expect(pathsWithError(initialValues)).toEqual(
      expect.arrayContaining([
        'step1.nome',
        'step4.bateria.subestacao',
        'step4.bateria.potencia_mw',
        'step4.bateria.capacidade_mwh',
        'step4.equipamento.cod_equipamento',
        'step4.equipamento.ganho_limite_mw',
        'step5.taxa_desconto_aa',
        'step5.horizonte_anos',
        'step5.capex_reais',
      ]),
    )
  })

  it('the question is optional', () => {
    const data = validForm()
    data.step1.pergunta = ''
    expect(pathsWithError(data)).not.toContain('step1.pergunta')
  })

  it("a block the modality doesn't ask for isn't required", () => {
    const data = validForm()
    data.step3.modalidade = 'bateria'
    data.step4.equipamento = { ...initialValues.step4.equipamento }
    expect(pathsWithError(data)).toEqual([])

    data.step3.modalidade = 'equipamento'
    data.step4.bateria = { ...initialValues.step4.bateria }
    data.step4.equipamento = validForm().step4.equipamento
    expect(pathsWithError(data)).toEqual([])
  })

  it("checks the motor's limits", () => {
    const data = validForm()
    data.step4.bateria.potencia_mw = 0
    data.step4.bateria.eficiencia_ida_volta = 1.2
    data.step4.bateria.vida_util_anos = 15.5
    data.step5.taxa_desconto_aa = 1
    data.step5.capex_reais = Number.NaN
    expect(pathsWithError(data)).toEqual(
      expect.arrayContaining([
        'step4.bateria.potencia_mw',
        'step4.bateria.eficiencia_ida_volta',
        'step4.bateria.vida_util_anos',
        'step5.taxa_desconto_aa',
        'step5.capex_reais',
      ]),
    )
  })

  it('requires min <= initial <= max charge, when all three are filled', () => {
    const data = validForm()
    data.step4.bateria.soc_min = 0.2
    data.step4.bateria.soc_max = 0.8
    data.step4.bateria.soc_inicial = 0.9
    expect(pathsWithError(data)).toContain('step4.bateria.soc_inicial')

    data.step4.bateria.soc_inicial = 0.5
    expect(pathsWithError(data)).toEqual([])

    data.step4.bateria.soc_min = 0.9
    expect(pathsWithError(data)).toContain('step4.bateria.soc_min')
  })

  it('empty initial charge assumes the minimum, so omitting it is never an error', () => {
    const data = validForm()
    data.step4.bateria.soc_min = 0.3
    data.step4.bateria.soc_max = 0.8
    data.step4.bateria.soc_inicial = null
    expect(pathsWithError(data)).toEqual([])

    data.step4.bateria.soc_min = null
    data.step4.bateria.soc_max = null
    expect(pathsWithError(data)).toEqual([])
  })

  it('an inverted range is rejected on its own, without initial charge, naming both values', () => {
    const data = validForm()
    data.step4.bateria.soc_min = 0.9
    data.step4.bateria.soc_max = 0.4
    data.step4.bateria.soc_inicial = null

    expect(messageAt(data, 'step4.bateria.soc_min')).toBe(
      'A carga mínima (0,9) não pode passar da máxima (0,4).',
    )
  })

  it('checks initial charge only against the limit that was filled', () => {
    const data = validForm()
    data.step4.bateria.soc_min = 0.3
    data.step4.bateria.soc_inicial = 0.1
    expect(messageAt(data, 'step4.bateria.soc_inicial')).toBe(
      'Deve ser maior ou igual à carga mínima (0,3).',
    )

    data.step4.bateria.soc_min = null
    data.step4.bateria.soc_max = 0.6
    data.step4.bateria.soc_inicial = 0.7
    expect(messageAt(data, 'step4.bateria.soc_inicial')).toBe(
      'Deve ser menor ou igual à carga máxima (0,6).',
    )

    data.step4.bateria.soc_inicial = 0.6
    expect(pathsWithError(data)).toEqual([])
  })

  it('each replacement requires year and value', () => {
    const data = validForm()
    data.step5.reposicoes = [{ ano: null, valor_reais: null }]
    expect(pathsWithError(data)).toEqual(
      expect.arrayContaining(['step5.reposicoes.0.ano', 'step5.reposicoes.0.valor_reais']),
    )
  })
})

/** A mensagem do primeiro erro do caminho, como o campo a mostra. */
function messageAt(data: SimulationFormData, path: string): string | undefined {
  const result = formSchema.safeParse(data)
  return result.success
    ? undefined
    : result.error.issues.find((issue) => issue.path.join('.') === path)?.message
}

describe('numeric field limits', () => {
  it('range (0, 1]: below, at the minimum, valid, at the maximum, above', () => {
    const data = validForm()
    const path = 'step4.bateria.disponibilidade'
    const hasError = (value: number) => {
      data.step4.bateria.disponibilidade = value
      return pathsWithError(data).includes(path)
    }
    expect(hasError(-0.1)).toBe(true)
    expect(hasError(0)).toBe(true) // exclusivo: zero não vale
    expect(hasError(0.01)).toBe(false)
    expect(hasError(0.85)).toBe(false)
    expect(hasError(1)).toBe(false) // inclusivo: um vale
    expect(hasError(1.01)).toBe(true)
  })

  it('exclusive (>0 and <1) rejects exactly the limit', () => {
    const data = validForm()
    data.step5.taxa_desconto_aa = 0
    expect(pathsWithError(data)).toEqual([])
    data.step5.taxa_desconto_aa = 1
    expect(messageAt(data, 'step5.taxa_desconto_aa')).toBe('Deve ser menor que 1.')

    data.step5.taxa_desconto_aa = 0.09
    data.step4.bateria.potencia_mw = 0
    expect(messageAt(data, 'step4.bateria.potencia_mw')).toBe('Deve ser maior que 0.')
    data.step4.bateria.potencia_mw = 0.01
    expect(pathsWithError(data)).toEqual([])
  })

  it('integer rejects a fraction and accepts the minimum', () => {
    const data = validForm()
    data.step5.horizonte_anos = 0
    expect(messageAt(data, 'step5.horizonte_anos')).toBe('Deve ser maior que 0.')
    data.step5.horizonte_anos = 10.5
    expect(messageAt(data, 'step5.horizonte_anos')).toBe('Informe um número inteiro.')
    data.step5.horizonte_anos = 1
    expect(pathsWithError(data)).toEqual([])
  })

  it('money gives the limit in reais', () => {
    const data = validForm()
    data.step5.capex_reais = -1
    expect(messageAt(data, 'step5.capex_reais')).toBe('Deve ser maior ou igual a R$ 0,00.')
    data.step5.capex_reais = 0
    expect(pathsWithError(data)).toEqual([])
  })

  it('empty required field is an error and never becomes zero', () => {
    const data = validForm()
    data.step5.capex_reais = null
    expect(messageAt(data, 'step5.capex_reais')).toBe('Campo obrigatório.')
  })

  it('empty optional passes, and NaN does not', () => {
    const data = validForm()
    data.step5.opex_fixo_reais_ano = null
    expect(pathsWithError(data)).toEqual([])
    data.step5.opex_fixo_reais_ano = Number.NaN
    expect(messageAt(data, 'step5.opex_fixo_reais_ano')).toBe('Informe um valor válido.')
  })
})

describe('submit', () => {
  it("does not send the block the modality doesn't accept, but doesn't erase what was typed", () => {
    const data = validForm()
    data.step3.modalidade = 'bateria'
    const envio = dataForModality(data)
    expect(envio.step4.equipamento).toBeUndefined()
    expect(envio.step4.bateria?.potencia_mw).toBe(100)
    expect(data.step4.equipamento.cod_equipamento).toBe('FICT-A1')
  })
})

describe('steps', () => {
  it('every step has declared fields', () => {
    for (const step of STEPS) expect(stepFields[step].length).toBeGreaterThan(0)
  })

  it('step 4 only validates the block the modality shows', () => {
    const batteryOnly = visibleFields(4, 'bateria')
    expect(batteryOnly.every((field) => field.startsWith('step4.bateria'))).toBe(true)
    const circuitOnly = visibleFields(4, 'equipamento')
    expect(circuitOnly.every((field) => field.startsWith('step4.equipamento'))).toBe(true)
    expect(visibleFields(4, 'combinada')).toHaveLength(stepFields[4].length)
  })

  it("links the premise's field to the form field", () => {
    expect(fieldForPremise('bateria.disponibilidade')).toBe('step4.bateria.disponibilidade')
    expect(fieldForPremise('financeira.horizonte_anos')).toBe('step5.horizonte_anos')
    expect(fieldForPremise('financeira.nao_existe')).toBeUndefined()
  })
})
