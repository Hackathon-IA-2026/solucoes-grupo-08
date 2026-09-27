import { useEffect, useState } from 'react'

/** Tempo entre um cartão e o seguinte, e o menor passo quando há muitos na fila. */
export const REVEAL_MS = 450
export const REVEAL_MIN_MS = 70
/**
 * Quantos passos calmos cabem na fila antes de ela acelerar: com `waiting` cartões esperando, o
 * passo é `REVEAL_MS * REVEAL_BACKLOG / waiting`, entre o mínimo e o calmo. Até 3 na fila é o
 * passo calmo; com 30, cai a 45 ms (e o piso segura em 70).
 */
export const REVEAL_BACKLOG = 3

/**
 * Solta os nós um por vez, na ordem em que vêm, para o grafo se montar cartão a cartão em vez de
 * aparecer de uma vez. Os eventos chegam em rajada (uma rodada decidida traz as variações juntas,
 * e uma exploração já terminada chega inteira), e a fila é o que dá o ritmo. O primeiro entra na
 * hora; com pouca coisa esperando o passo é calmo, e com muita ele acelera, para uma exploração
 * já terminada não levar um minuto para se desenhar. Um nó que já entrou não sai, e o que chega depois entra no fim da fila.
 */
export function useRevealQueue(nodes: readonly { id: string }[]) {
  const [revealed, setRevealed] = useState<ReadonlySet<string>>(() => new Set())
  // O id, e não o nó: o grafo é refeito a cada medição de altura, e um nó novo a cada vez
  // reiniciaria o tempo de espera do cartão que já está na fila.
  const next = nodes.find((node) => !revealed.has(node.id))?.id
  const waiting = nodes.filter((node) => !revealed.has(node.id)).length

  useEffect(() => {
    if (next === undefined) return
    const delay =
      revealed.size === 0
        ? 0
        : Math.max(REVEAL_MIN_MS, Math.min(REVEAL_MS, (REVEAL_MS * REVEAL_BACKLOG) / waiting))
    const timer = window.setTimeout(
      () => setRevealed((current) => new Set(current).add(next)),
      delay,
    )
    return () => window.clearTimeout(timer)
  }, [next, revealed.size, waiting])

  return { revealed, waiting }
}
