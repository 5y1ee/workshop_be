import { createContext, useContext, useState, type ReactNode } from 'react'
import { useAuth } from './auth'
import { useWebSocket, type WsEvent } from './useWebSocket'

interface LiveState {
  connected: boolean
  lastEvent: WsEvent | null
  log: string[]
}

const LiveContext = createContext<LiveState | null>(null)
const LOG_LIMIT = 30

/** 앱 전체에서 단일 WebSocket 연결을 공유한다. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null)
  const [log, setLog] = useState<string[]>([])

  const { connected } = useWebSocket(token, (e) => {
    setLastEvent(e)
    const sid = e.session_id as number | undefined
    const desc =
      e.type === 'score_recorded'
        ? `점수 기록 (세션 #${sid})`
        : e.type === 'result_recorded'
          ? `결과 확정 (세션 #${sid})`
          : e.type === 'session_state_changed'
            ? `상태 → ${e.state} (세션 #${sid})`
            : e.type === 'roulette_result'
              ? `🎰 룰렛 → ${e.selected} (세션 #${sid})`
              : null
    if (desc) {
      setLog((prev) =>
        [`${new Date().toLocaleTimeString()} · ${desc}`, ...prev].slice(0, LOG_LIMIT),
      )
    }
  })

  return (
    <LiveContext.Provider value={{ connected, lastEvent, log }}>
      {children}
    </LiveContext.Provider>
  )
}

export function useLive(): LiveState {
  const ctx = useContext(LiveContext)
  if (!ctx) throw new Error('useLive must be used within LiveProvider')
  return ctx
}
