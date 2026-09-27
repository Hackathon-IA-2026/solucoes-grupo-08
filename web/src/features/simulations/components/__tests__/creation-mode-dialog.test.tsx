import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CreationModeDialog } from '../creation-mode-dialog'
import { DEFAULT_AGENT_PROMPT } from '../../form/creation-mode'

afterEach(cleanup)

function renderDialog(props: Partial<Parameters<typeof CreationModeDialog>[0]> = {}) {
  const onConfirm = vi.fn()
  const onOpenChange = vi.fn()
  render(
    <CreationModeDialog
      open
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
      creating={false}
      {...props}
    />,
  )
  return { onConfirm, onOpenChange }
}

const button = (name: string) => screen.getByRole('button', { name })
const radio = (name: RegExp) => screen.getByRole('radio', { name })

describe('creation mode dialog', () => {
  it('asks how to create, with "Simulação normal" selected first', () => {
    renderDialog()

    expect(screen.getByText('Como você deseja criar sua simulação?')).toBeTruthy()
    expect(radio(/Simulação normal/).getAttribute('aria-checked')).toBe('true')
    expect(radio(/Com agentes/).getAttribute('aria-checked')).toBe('false')
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('confirms a normal simulation without any extra field', () => {
    const { onConfirm } = renderDialog()

    fireEvent.click(button('Continuar'))
    expect(screen.queryByRole('textbox')).toBeNull()
    fireEvent.click(button('Criar simulação'))

    expect(onConfirm).toHaveBeenCalledWith({ mode: 'normal' })
  })

  it('with agents, shows the instructions already filled with the default prompt', () => {
    renderDialog()

    fireEvent.click(radio(/Com agentes/))
    expect(radio(/Com agentes/).getAttribute('aria-checked')).toBe('true')
    fireEvent.click(button('Continuar'))

    const prompt = screen.getByLabelText('Instruções para os agentes') as HTMLTextAreaElement
    expect(prompt.value).toBe(DEFAULT_AGENT_PROMPT)
    expect(button('Criar simulação com agentes')).toBeTruthy()
  })

  it('sends the edited instructions', () => {
    const { onConfirm } = renderDialog()

    fireEvent.click(radio(/Com agentes/))
    fireEvent.click(button('Continuar'))
    fireEvent.change(screen.getByLabelText('Instruções para os agentes'), {
      target: { value: '  varie só a potência  ' },
    })
    fireEvent.click(button('Criar simulação com agentes'))

    expect(onConfirm).toHaveBeenCalledWith({ mode: 'agents', agentPrompt: 'varie só a potência' })
  })

  it('does not create with empty instructions, and says why', () => {
    const { onConfirm } = renderDialog()

    fireEvent.click(radio(/Com agentes/))
    fireEvent.click(button('Continuar'))
    fireEvent.change(screen.getByLabelText('Instruções para os agentes'), {
      target: { value: '   ' },
    })
    fireEvent.click(button('Criar simulação com agentes'))

    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toContain('Escreva as instruções')
  })

  it('"Voltar" returns to the choice, keeping what was written', () => {
    renderDialog()

    fireEvent.click(radio(/Com agentes/))
    fireEvent.click(button('Continuar'))
    fireEvent.change(screen.getByLabelText('Instruções para os agentes'), {
      target: { value: 'meu texto' },
    })
    fireEvent.click(button('Voltar'))
    expect(radio(/Com agentes/).getAttribute('aria-checked')).toBe('true')

    fireEvent.click(button('Continuar'))
    expect((screen.getByLabelText('Instruções para os agentes') as HTMLTextAreaElement).value).toBe(
      'meu texto',
    )
  })

  it('"Cancelar" closes the dialog', () => {
    const { onOpenChange } = renderDialog()

    fireEvent.click(button('Cancelar'))

    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('while creating, locks the buttons', () => {
    renderDialog({ creating: true })
    fireEvent.click(button('Continuar'))

    expect(button('Criando…')).toHaveProperty('disabled', true)
    expect(button('Voltar')).toHaveProperty('disabled', true)
  })

  it('once the simulation was saved, shows the error and does not let it be created again', () => {
    renderDialog({ error: 'os agentes não começaram', confirmDisabled: true })
    fireEvent.click(button('Continuar'))

    expect(screen.getByRole('alert').textContent).toContain('os agentes não começaram')
    expect(button('Criar simulação')).toHaveProperty('disabled', true)
  })
})
