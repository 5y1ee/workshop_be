import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useAuth } from './auth'
import { useWebSocket, type WsEvent } from './useWebSocket'

type Subscriber = (e: WsEvent) => void

interface LiveState {
  connected: boolean
  lastEvent: WsEvent | null
  log: string[]
  send: (message: Record<string, unknown>) => boolean
  /** 모든 수신 이벤트를 구독한다. 채팅처럼 누적이 필요한 화면용. 해지 함수를 반환. */
  subscribe: (fn: Subscriber) => () => void
}

const LiveContext = createContext<LiveState | null>(null)
const LOG_LIMIT = 30

/** 앱 전체에서 단일 WebSocket 연결을 공유한다. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null)
  const [log, setLog] = useState<string[]>([])
  const subscribers = useRef<Set<Subscriber>>(new Set())

  const { connected, send } = useWebSocket(token, (e) => {
    setLastEvent(e)
    subscribers.current.forEach((fn) => fn(e))
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
              : e.type === 'round_started'
                ? `▶️ 라운드 ${e.order_index} 시작 (세션 #${sid})`
                  : e.type === 'round_revealed'
                  ? `✅ 라운드 ${e.order_index} 정답: ${e.correct_answer} (세션 #${sid})`
                  : e.type === 'reward_claimed'
                  ? `🎁 ${e.nickname} → ${e.reward_name} 당첨!`
                  : e.type === 'reward_unclaimed'
                  ? `↩️ 리워드 #${e.reward_id} 수령 취소`
                  : null
    if (desc) {
      setLog((prev) =>
        [`${new Date().toLocaleTimeString()} · ${desc}`, ...prev].slice(0, LOG_LIMIT),
      )
    }
  })

  const subscribe = useRef((fn: Subscriber) => {
    subscribers.current.add(fn)
    return () => {
      subscribers.current.delete(fn)
    }
  }).current

  return (
    <LiveContext.Provider value={{ connected, lastEvent, log, send, subscribe }}>
      {children}
    </LiveContext.Provider>
  )
}

export function useLive(): LiveState {
  const ctx = useContext(LiveContext)
  if (!ctx) throw new Error('useLive must be used within LiveProvider')
  return ctx
}

/** 특정 이벤트 타입만 구독하는 헬퍼 훅. */
export function useLiveEvent(types: string[], handler: (e: WsEvent) => void) {
  const { subscribe } = useLive()
  const handlerRef = useRef(handler)
  handlerRef.current = handler
  useEffect(() => {
    return subscribe((e) => {
      if (types.includes(e.type)) handlerRef.current(e)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscribe, types.join(',')])
}
