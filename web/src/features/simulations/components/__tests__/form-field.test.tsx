import { zodResolver } from '@hookform/resolvers/zod'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { FormProvider, useForm } from 'react-hook-form'
import { afterEach, describe, expect, it } from 'vitest'
import type { FormFieldPath } from '../../form/constants'
import { formSchema, initialValues, type SimulationFormData } from '../../form/schema'
import { NumericField } from '../form-field'
import { TooltipProvider } from '@/components/ui/tooltip'

afterEach(cleanup)

type Form = ReturnType<typeof useForm<SimulationFormData>>

/** Um formulário com os campos reais, para testar o que o usuário vê e o que o formulário guarda. */
function renderForm(defaults: SimulationFormData = initialValues) {
  const handle: { form?: Form } = {}

  function Harness() {
    const form = useForm<SimulationFormData>({
      resolver: zodResolver(formSchema),
      mode: 'onChange',
      defaultValues: defaults,
    })
    handle.form = form
    return (
      <FormProvider {...form}>
        <TooltipProvider>
          <NumericField
            name="step5.capex_reais"
            kind="money"
            label="Investimento"
            unit="R$"
            required
          />
          <NumericField
            name="step5.horizonte_anos"
            kind="integer"
            label="Horizonte"
            unit="anos"
            required
          />
          <NumericField name="step4.bateria.eficiencia_ida_volta" label="Eficiência" unit="0 a 1" />
          <NumericField
            name="step5.taxa_desconto_aa"
            label="Taxa de desconto"
            unit="0 a 1 ao ano"
            tooltip="CAPEX: custo total de implantar a intervenção, em reais, no ano zero."
          />
        </TooltipProvider>
      </FormProvider>
    )
  }

  render(<Harness />)
  const value = (path: FormFieldPath) => handle.form!.getValues(path)
  return {
    handle,
    value,
    field: (label: string | RegExp) => screen.getByLabelText(label) as HTMLInputElement,
  }
}

/** Digita como o navegador: cada tecla chega como o texto inteiro do campo, com a tecla no fim. */
function type(input: HTMLInputElement, keys: string) {
  for (const key of keys) fireEvent.change(input, { target: { value: input.value + key } })
}

describe('creation: empty → user types → form', () => {
  it('money: stores the number and shows the mask', () => {
    const { field, value } = renderForm()
    const capex = field(/Investimento/)

    expect(capex.value).toBe('')
    type(capex, '125050')

    expect(capex.value).toBe('1.250,50')
    expect(value('step5.capex_reais')).toBe(1250.5)
  })

  it('money pasted with symbol and thousands separator', () => {
    const { field, value } = renderForm()
    const capex = field(/Investimento/)

    fireEvent.paste(capex, { clipboardData: { getData: () => 'R$ 1.250,50' } })

    expect(capex.value).toBe('1.250,50')
    expect(value('step5.capex_reais')).toBe(1250.5)
  })

  it('integer: rejects letter, sign and decimal', () => {
    const { field, value } = renderForm()
    const years = field(/Horizonte/)

    fireEvent.change(years, { target: { value: 'abc' } })
    expect(years.value).toBe('')
    expect(value('step5.horizonte_anos')).toBeNull()

    fireEvent.change(years, { target: { value: '-10' } })
    expect(years.value).toBe('10')

    fireEvent.change(years, { target: { value: '10.5' } })
    expect(years.value).toBe('10')
    expect(value('step5.horizonte_anos')).toBe(10)
  })

  it('decimal: keeps the comma while typing and stores a dot in the number', () => {
    const { field, value } = renderForm()
    const efficiency = field(/Eficiência/)

    type(efficiency, '0,')
    expect(efficiency.value).toBe('0,')
    expect(value('step4.bateria.eficiencia_ida_volta')).toBe(0)

    type(efficiency, '85')
    expect(efficiency.value).toBe('0,85')
    expect(value('step4.bateria.eficiencia_ida_volta')).toBe(0.85)
  })

  it('decimal: accepts a dot as the decimal separator and strips the rest', () => {
    const { field, value } = renderForm()
    const efficiency = field(/Eficiência/)

    fireEvent.change(efficiency, { target: { value: '0.85x' } })
    expect(efficiency.value).toBe('0,85')
    expect(value('step4.bateria.eficiencia_ida_volta')).toBe(0.85)
  })

  it('decimal: a trailing comma disappears on blur', () => {
    const { field } = renderForm()
    const efficiency = field(/Eficiência/)

    type(efficiency, '1,')
    fireEvent.blur(efficiency)
    expect(efficiency.value).toBe('1')
  })
})

describe('edit: API → form → user edits', () => {
  const fromApi: SimulationFormData = {
    ...initialValues,
    step5: {
      ...initialValues.step5,
      capex_reais: 1250.5,
      horizonte_anos: 20,
    },
    step4: {
      ...initialValues.step4,
      bateria: { ...initialValues.step4.bateria, eficiencia_ida_volta: 0.85 },
    },
  }

  it('shows the value that came from the API, without shifting decimal places', () => {
    const { field } = renderForm(fromApi)

    expect(field(/Investimento/).value).toBe('1.250,50')
    expect(field(/Horizonte/).value).toBe('20')
    expect(field(/Eficiência/).value).toBe('0,85')
  })

  it('editing over it stays a number', () => {
    const { field, value } = renderForm(fromApi)

    fireEvent.change(field(/Investimento/), { target: { value: '1.250,505' } })
    expect(value('step5.capex_reais')).toBe(12505.05)
  })

  it('a premise value that arrives later enters the field', () => {
    const { field, handle } = renderForm()

    act(() => handle.form!.setValue('step5.capex_reais', 1500000))
    act(() => handle.form!.setValue('step4.bateria.eficiencia_ida_volta', 0.9))

    expect(field(/Investimento/).value).toBe('1.500.000,00')
    expect(field(/Eficiência/).value).toBe('0,9')
  })
})

describe('reset, validation and submit', () => {
  it('reset clears the fields', () => {
    const { field, handle } = renderForm()
    type(field(/Investimento/), '100')
    type(field(/Eficiência/), '0,5')

    act(() => handle.form!.reset())

    expect(field(/Investimento/).value).toBe('')
    expect(field(/Eficiência/).value).toBe('')
  })

  it('error appears linked to the field, with the limit message', async () => {
    const { field, handle } = renderForm()
    const efficiency = field(/Eficiência/)

    type(efficiency, '1,5')
    await act(() => handle.form!.trigger('step4.bateria.eficiencia_ida_volta'))

    await waitFor(() => expect(efficiency.getAttribute('aria-invalid')).toBe('true'))
    const message = screen.getByRole('alert')
    expect(message.textContent).toBe('Deve ser menor ou igual a 1.')
    expect(efficiency.getAttribute('aria-describedby')).toBe(message.id)
  })

  it('empty required field does not become zero on validation', async () => {
    const { handle, value } = renderForm()

    await act(() => handle.form!.trigger('step5.capex_reais'))

    expect(value('step5.capex_reais')).toBeNull()
    expect(screen.getByRole('alert').textContent).toBe('Campo obrigatório.')
  })

  it("the mobile keyboard matches the field's type", () => {
    const { field } = renderForm()

    expect(field(/Investimento/).inputMode).toBe('numeric')
    expect(field(/Horizonte/).inputMode).toBe('numeric')
    expect(field(/Eficiência/).inputMode).toBe('decimal')
  })

  it('the label stays linked to the field', () => {
    renderForm()

    expect(screen.getByLabelText(/Horizonte/).id).toBe('campo-step5-horizonte_anos')
  })

  it('shows the tooltip next to the label when the field has one', async () => {
    renderForm()

    fireEvent.focus(screen.getByRole('button', { name: 'Ajuda: Taxa de desconto' }))
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip.textContent).toContain('CAPEX')
  })
})
