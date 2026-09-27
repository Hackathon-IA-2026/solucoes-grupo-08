import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { FormProvider, useForm } from 'react-hook-form'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { initialValues, type SimulationFormData } from '../../form/schema'
import { StepModality } from '../step-modality'
import { TooltipProvider } from '@/components/ui/tooltip'

afterEach(cleanup)

function renderStep() {
  function Harness() {
    const form = useForm<SimulationFormData>({ defaultValues: initialValues })
    return (
      <FormProvider {...form}>
        <TooltipProvider>
          <StepModality onBack={vi.fn()} onContinue={vi.fn()} />
        </TooltipProvider>
      </FormProvider>
    )
  }

  return render(<Harness />)
}

describe('step modality', () => {
  it('explains the word "Modalidade" in a tooltip on the title', async () => {
    renderStep()

    fireEvent.focus(screen.getByRole('button', { name: 'Ajuda: Modalidade' }))
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip.textContent).toContain('bateria, adição de')
  })
})
