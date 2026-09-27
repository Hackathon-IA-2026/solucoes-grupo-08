import type { SimulationModality } from '../api/simulation-modality'
import './modality-illustration.css'

function Battery() {
  return (
    <svg width="200" height="96" viewBox="0 0 200 96" className="max-w-full">
      <rect
        x="52"
        y="28"
        width="96"
        height="40"
        rx="6"
        fill="none"
        stroke="var(--mi-stroke)"
        strokeWidth="2"
      />
      <rect x="150" y="40" width="8" height="16" rx="2" fill="var(--mi-stroke)" />
      <rect className="mi-cell" x="60" y="36" width="18" height="24" rx="2" />
      <rect className="mi-cell mi-c2" x="82" y="36" width="18" height="24" rx="2" />
      <rect className="mi-cell mi-c3" x="104" y="36" width="18" height="24" rx="2" />
      <rect className="mi-cell mi-c4" x="126" y="36" width="18" height="24" rx="2" />
      <g
        className="mi-arrow-in"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 48h28" />
        <path d="M32 40l8 8-8 8" />
      </g>
      <g
        className="mi-arrow-out"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M166 48h24" />
        <path d="M182 40l8 8-8 8" />
      </g>
    </svg>
  )
}

/** Duas subestações, a linha existente em `yExistente` e o circuito novo em `yNovo`. */
function Circuits({ yExistente, yNovo }: { yExistente: number; yNovo: number }) {
  return (
    <>
      <circle cx="24" cy="48" r="9" stroke="var(--mi-stroke)" strokeWidth="2" fill="var(--mi-bg)" />
      <circle
        cx="176"
        cy="48"
        r="9"
        stroke="var(--mi-stroke)"
        strokeWidth="2"
        fill="var(--mi-bg)"
      />
      <path
        d={`M33 ${yExistente} L167 ${yExistente}`}
        stroke="var(--mi-idle)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        className="mi-flow"
        d={`M33 ${yExistente} L167 ${yExistente}`}
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      <path
        className="mi-newline"
        d={`M33 ${yNovo} L167 ${yNovo}`}
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      <path
        className="mi-flow2"
        d={`M33 ${yNovo} L167 ${yNovo}`}
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
    </>
  )
}

function Circuit() {
  return (
    <svg width="200" height="96" viewBox="0 0 200 96" className="max-w-full">
      <Circuits yExistente={40} yNovo={58} />
    </svg>
  )
}

function Combined() {
  return (
    <svg width="200" height="96" viewBox="0 0 200 96" className="max-w-full">
      <Circuits yExistente={34} yNovo={48} />
      <path d="M24 57v10h48" stroke="var(--mi-stroke)" strokeWidth="2" fill="none" />
      <rect
        x="72"
        y="62"
        width="56"
        height="22"
        rx="4"
        fill="none"
        stroke="var(--mi-stroke)"
        strokeWidth="2"
      />
      <rect x="129" y="69" width="5" height="8" rx="1" fill="var(--mi-stroke)" />
      <rect className="mi-cell" x="77" y="67" width="10" height="12" rx="1" />
      <rect className="mi-cell mi-c2" x="90" y="67" width="10" height="12" rx="1" />
      <rect className="mi-cell mi-c3" x="103" y="67" width="10" height="12" rx="1" />
      <rect className="mi-cell mi-c4" x="116" y="67" width="10" height="12" rx="1" />
    </svg>
  )
}

const ilustracoes: Record<SimulationModality, () => React.JSX.Element> = {
  bateria: Battery,
  equipamento: Circuit,
  combinada: Combined,
}

/** Ilustração animada de cada modalidade. Decorativa: o cartão já nomeia a opção. */
export function ModalityIllustration({ modality }: { modality: SimulationModality }) {
  const Ilustracao = ilustracoes[modality]

  return (
    <div
      aria-hidden="true"
      className="modality-illustration flex h-30 w-full items-center justify-center rounded-md bg-surface-secondary"
    >
      <Ilustracao />
    </div>
  )
}
