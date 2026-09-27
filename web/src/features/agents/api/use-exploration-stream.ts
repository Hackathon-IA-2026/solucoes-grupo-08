import { useEffect, useReducer, useRef, useState } from 'react'
import { EVENT_TYPES, eventsUrl, type ExplorationEvent, type RecordedEvent } from './exploration'
import { applyRecordedEvent, emptyExploration, type ExplorationState } from './exploration-state'

export type Connection = 'connecting' | 'live' | 'reconnecting' | 'closed'

function reducer(state: ExplorationState, event: RecordedEvent): ExplorationState {
  return applyRecordedEvent(state, event)
}

/**
 * Segue o streaming de uma exploração e monta o estado dela. Uma conexão só basta para montar a
 * tela do zero, inclusive de uma tarefa já terminada: a API manda tudo que já foi gravado.
 *
 * Uma exploração por montagem: quem troca de `taskId` remonta o componente (`key`), então o estado
 * nasce vazio e não precisa ser zerado aqui. O `EventSource` reconecta sozinho e manda o `Last-Event-ID`; ao receber `tarefa_terminada` a
 * tela fecha a conexão, senão ele tentaria reconectar num streaming que já fechou.
 */
export function useExplorationStream(taskId: number, onEvent?: (event: ExplorationEvent) => void) {
  const [state, dispatch] = useReducer(reducer, emptyExploration)
  const [connection, setConnection] = useState<Connection>('connecting')
  const onEventRef = useRef(onEvent)
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!Number.isFinite(taskId)) return
    const source = new EventSource(eventsUrl(taskId))

    const listeners = EVENT_TYPES.map((type) => {
      const listener = (message: Event) => {
        const recorded = JSON.parse((message as MessageEvent<string>).data) as RecordedEvent
        dispatch(recorded)
        onEventRef.current?.(recorded.evento)
        if (recorded.evento.tipo === 'tarefa_terminada') {
          source.close()
          setConnection('closed')
        }
      }
      source.addEventListener(type, listener)
      return [type, listener] as const
    })

    source.onopen = () => setConnection('live')
    source.onerror = () =>
      // Fechada de vez (404, ou o navegador desistiu): não há o que reconectar.
      setConnection(source.readyState === EventSource.CLOSED ? 'closed' : 'reconnecting')

    return () => {
      for (const [type, listener] of listeners) source.removeEventListener(type, listener)
      source.close()
    }
  }, [taskId])

  return { state, connection }
}
