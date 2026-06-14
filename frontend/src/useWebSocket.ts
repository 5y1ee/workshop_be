import { useEffect, useRef, useState } from 'react'
import { wsUrl } from './api'

export interface WsEvent {
  type: string
  [key: string]: unknown
}

/** 토큰으로 /ws 에 연결하고 수신 메시지를 onEvent 로 전달한다. */
export function useWebSocket(token: string | null, onEvent: (e: WsEvent) => void) {
  const [connected, setConnected] = useState(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    if (!token) return
    const ws = new WebSocket(wsUrl(token))
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (ev) => {
      try {
        onEventRef.current(JSON.parse(ev.data) as WsEvent)
      } catch {
        // JSON 이 아닌 메시지는 무시
      }
    }
    return () => ws.close()
  }, [token])

  return { connected }
}
