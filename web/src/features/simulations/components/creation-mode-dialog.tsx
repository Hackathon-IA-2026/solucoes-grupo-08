import { Bot, Calculator } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import {
  DEFAULT_AGENT_PROMPT,
  MAX_AGENT_PROMPT,
  type CreationChoice,
  type SimulationCreationMode,
} from '../form/creation-mode'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/utils/cn'

type CreationModeDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (choice: CreationChoice) => void
  /** Enquanto a criação está em curso: os botões ficam presos e o modal não fecha. */
  creating: boolean
  /** Falha da criação, do salvamento ou do começo da exploração. */
  error?: ReactNode
  /** A simulação já foi salva: criar de novo duplicaria. */
  confirmDisabled?: boolean
}

const options: {
  id: SimulationCreationMode
  title: string
  description: string
  icon: ReactNode
}[] = [
    {
      id: 'normal',
      title: 'Simulação normal',
      description: 'Crie uma simulação sem agentes.',
      icon: <Calculator className="size-5" aria-hidden="true" />,
    },
    {
      id: 'agents',
      title: 'Com agentes',
      description: 'Crie uma simulação utilizando agentes configurados a partir de uma instrução.',
      icon: <Bot className="size-5" aria-hidden="true" />,
    },
  ]

/**
 * A finalização da Nova simulação, em duas etapas: escolher como criar (normal ou com agentes) e
 * confirmar. Com agentes, a confirmação traz a instrução, que já nasce preenchida e pode ser
 * reescrita inteira. O modal só escolhe; quem cria é quem recebe `onConfirm`.
 */
export function CreationModeDialog({
  open,
  onOpenChange,
  onConfirm,
  creating,
  error,
  confirmDisabled = false,
}: CreationModeDialogProps) {
  const [stage, setStage] = useState<'choose' | 'confirm'>('choose')
  const [mode, setMode] = useState<SimulationCreationMode>('normal')
  const [agentPrompt, setAgentPrompt] = useState(DEFAULT_AGENT_PROMPT)
  const [showPromptError, setShowPromptError] = useState(false)
  const promptEmpty = agentPrompt.trim() === ''

  function confirm() {
    if (mode === 'normal') return onConfirm({ mode })
    if (promptEmpty) return setShowPromptError(true)
    onConfirm({ mode, agentPrompt: agentPrompt.trim() })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (creating) return
        onOpenChange(next)
        // Reabrir começa pela escolha; o texto da instrução fica como a pessoa deixou.
        if (!next) {
          setStage('choose')
          setShowPromptError(false)
        }
      }}
    >
      <DialogContent className="max-w-2xl">
        <DialogTitle className="sim-display text-(--sim-brand-ink)">
          {stage === 'choose'
            ? 'Como você deseja criar sua simulação?'
            : mode === 'agents'
              ? 'Criar simulação com agentes'
              : 'Criar simulação'}
        </DialogTitle>
        <DialogDescription className="text-(--sim-muted-foreground)">
          {stage === 'choose'
            ? 'Escolha antes de confirmar. Os valores do formulário são os mesmos nas duas opções.'
            : mode === 'agents'
              ? 'Descreva como os agentes devem se comportar nesta simulação, incluindo seus objetivos, características, regras e possíveis interações.'
              : 'A simulação é calculada e salva com os valores do formulário, sem agentes.'}
        </DialogDescription>

        {stage === 'choose' ? (
          <div
            role="radiogroup"
            aria-label="Como criar a simulação"
            className="mt-5 grid gap-3 sm:grid-cols-2"
          >
            {options.map((option) => {
              const selected = option.id === mode
              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setMode(option.id)}
                  className={cn(
                    'relative flex flex-col items-start gap-3 rounded-lg border bg-surface p-5 text-left transition-colors',
                    selected
                      ? 'border-primary ring-1 ring-primary'
                      : 'border-border hover:border-text-muted',
                  )}
                >
                  <span
                    className={cn(
                      'grid size-9 place-items-center rounded-lg',
                      selected
                        ? 'bg-(--sim-sky-soft) text-(--sim-brand)'
                        : 'bg-(--sim-muted) text-(--sim-muted-foreground)',
                    )}
                  >
                    {option.icon}
                  </span>
                  <span
                    className={cn(
                      'absolute top-4 right-4 h-4 w-4 rounded-full border-2',
                      selected ? 'border-primary bg-primary' : 'border-border bg-surface',
                    )}
                    aria-hidden="true"
                  />
                  <span className="flex flex-col gap-1">
                    <span className="text-sm font-semibold text-text-primary">{option.title}</span>
                    <span className="text-sm text-text-secondary">{option.description}</span>
                  </span>
                </button>
              )
            })}
          </div>
        ) : mode === 'agents' ? (
          <div className="mt-5 flex flex-col gap-2">
            <label htmlFor="instrucoes-agentes" className="sim-overview-label">
              Instruções para os agentes
            </label>
            <Textarea
              id="instrucoes-agentes"
              value={agentPrompt}
              onChange={(event) => {
                setAgentPrompt(event.target.value)
                if (event.target.value.trim() !== '') setShowPromptError(false)
              }}
              maxLength={MAX_AGENT_PROMPT}
              rows={10}
              autoFocus
              aria-invalid={showPromptError && promptEmpty}
              aria-describedby="instrucoes-agentes-ajuda"
              className="min-h-56 resize-y border-(--sim-border) bg-(--sim-surface) text-(--sim-foreground)"
            />
            <div className="flex items-start justify-between gap-4 text-xs">
              <span className="shrink-0 tabular-nums text-(--sim-muted-foreground)">
                {agentPrompt.length} / {MAX_AGENT_PROMPT}
              </span>
            </div>
            {showPromptError && promptEmpty && (
              <p role="alert" className="text-sm text-danger">
                Escreva as instruções para os agentes antes de criar.
              </p>
            )}
          </div>
        ) : null}

        {error && (
          <div role="alert" className="mt-4 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {stage === 'choose' ? (
            <>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="button" onClick={() => setStage('confirm')}>
                Continuar
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                disabled={creating}
                onClick={() => {
                  setStage('choose')
                  setShowPromptError(false)
                }}
              >
                Voltar
              </Button>
              <Button type="button" disabled={creating || confirmDisabled} onClick={confirm}>
                {creating
                  ? 'Criando…'
                  : mode === 'agents'
                    ? 'Criar simulação com agentes'
                    : 'Criar simulação'}
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
