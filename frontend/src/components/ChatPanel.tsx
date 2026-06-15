import { useEffect, useRef, useState } from 'react'
import { useLive } from '../live'
import type { GameRound } from '../api'

interface ChatMessage {
  key: number
  userId: number
  nickname: string
  message: string
  isCorrect: boolean
  time: string
}

interface Props {
  sessionId: number
  myUserId: number
  round: GameRound | null
}

/** input_type=chat 게임용 실시간 채팅. 현재 열린 라운드 기준으로 정답을 가린다. */
export default function ChatPanel({ sessionId, myUserId, round }: Props) {
  const { send, subscribe, connected } = useLive()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [text, setText] = useState('')
  const keyRef = useRef(0)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return subscribe((e) => {
      if (e.type !== 'chat_message' || e.session_id !== sessionId) return
      setMessages((prev) => [
        ...prev,
        {
          key: keyRef.current++,
          userId: e.user_id as number,
          nickname: (e.nickname as string) ?? '익명',
          message: e.message as string,
          isCorrect: Boolean(e.is_correct),
          time: e.server_time as string,
        },
      ])
    })
  }, [subscribe, sessionId])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages])

  const submit = () => {
    const msg = text.trim()
    if (!msg) return
    if (send({ type: 'chat_message', session_id: sessionId, message: msg })) {
      setText('')
    }
  }

  return (
    <section className="card chat">
      <div className="chat-head">
        <span className="op-label">💬 실시간 채팅</span>
        <span className={`dot ${connected ? 'on' : 'off'}`}>
          {connected ? '연결됨' : '연결 끊김'}
        </span>
      </div>

      {round ? (
        <div className="chat-round">
          <strong>문제 {round.order_index}</strong>
          {round.prompt && <span className="muted"> · {round.prompt}</span>}
          {round.media_url && (
            <audio className="chat-audio" src={round.media_url} controls preload="none" />
          )}
        </div>
      ) : (
        <p className="muted">진행 중인 라운드가 없습니다. 운영자가 문제를 열면 시작됩니다.</p>
      )}

      <div className="chat-list" ref={listRef}>
        {messages.length === 0 ? (
          <p className="muted chat-empty">아직 메시지가 없습니다. 정답을 입력해보세요!</p>
        ) : (
          messages.map((m) => (
            <div
              key={m.key}
              className={`chat-msg${m.userId === myUserId ? ' mine' : ''}${
                m.isCorrect ? ' correct' : ''
              }`}
            >
              <span className="chat-nick">{m.nickname}</span>
              <span className="chat-text">{m.message}</span>
              {m.isCorrect && <span className="chat-badge">정답 🎉</span>}
            </div>
          ))
        )}
      </div>

      <div className="chat-input">
        <input
          value={text}
          placeholder={round ? '정답 입력…' : '문제 대기 중'}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submit()
          }}
        />
        <button className="op-btn" onClick={submit} disabled={!text.trim()}>
          전송
        </button>
      </div>
    </section>
  )
}
