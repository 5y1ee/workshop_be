import { useCallback, useEffect, useRef, useState } from 'react'
import { wsUrl } from './api'

export interface WsEvent {
  type: string
  [key: string]: unknown
}

/** 토큰으로 /ws 에 연결하고 수신 메시지를 onEvent 로 전달한다. send 로 송신도 가능. */
export function useWebSocket(token: string | null, onEvent: (e: WsEvent) => void) {
  const [connected, setConnected] = useState(false)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!token) return
    const ws = new WebSocket(wsUrl(token))
    wsRef.current = ws
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
    return () => {
      wsRef.current = null
      ws.close()
    }
  }, [token])

  const send = useCallback((message: Record<string, unknown>) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
      return true
    }
    return false
  }, [])

  return { connected, send }
}
