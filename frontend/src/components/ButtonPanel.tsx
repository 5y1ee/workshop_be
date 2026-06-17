import { useEffect, useState } from 'react'
import { useLive } from '../live'
import type { GameRound } from '../api'

interface RevealInfo {
  correctAnswer: string | null
  distribution: Record<string, number>
  total: number
}

/** round_started 이벤트/prop 양쪽에서 받는 라운드 최소 정보. */
interface LiveRound {
  id: number
  order_index: number
  prompt: string | null
  options: string[] | null
  status: string
}

interface Props {
  sessionId: number
  round: GameRound | null
}

function roundToLive(r: GameRound | null): LiveRound | null {
  if (!r) return null
  return {
    id: r.id,
    order_index: r.order_index,
    prompt: r.prompt,
    options: r.options,
    status: r.status,
  }
}

function norm(v: string): string {
  return v.trim().toLowerCase()
}

/** input_type=button 게임용 보기 선택. 라운드별 1인 1답. */
export default function ButtonPanel({ sessionId, round }: Props) {
  const { send, subscribe } = useLive()
  // round prop 이 null 이 되어도(마감 후) 결과 화면을 유지하기 위해 내부 state 로 보존
  const [active, setActive] = useState<LiveRound | null>(() => roundToLive(round))
  const [selected, setSelected] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [progress, setProgress] = useState(0)
  const [reveal, setReveal] = useState<RevealInfo | null>(null)

  // prop 갱신 동기화 — 단, round=null 로는 결과 화면을 끄지 않는다.
  useEffect(() => {
    if (round) setActive(roundToLive(round))
  }, [round])

  // 라운드 id 가 진짜 바뀔 때만 진행 상태 초기화 (close → null 사이클에서 reveal 보존)
  useEffect(() => {
    setSelected(null)
    setSubmitted(false)
    setProgress(0)
    setReveal(null)
  }, [active?.id])

  useEffect(() => {
    return subscribe((e) => {
      if (e.session_id !== sessionId) return

      // 운영자가 새 문제를 오픈하면 즉시 패널 전환
      if (e.type === 'round_started') {
        setActive({
          id: e.round_id as number,
          order_index: (e.order_index as number) ?? 0,
          prompt: (e.prompt as string | null) ?? null,
          options: (e.options as string[] | null) ?? null,
          status: (e.status as string) ?? 'open',
        })
        return
      }
      if (e.type === 'submission_progress' && e.round_id === active?.id) {
        setProgress(e.submitted as number)
      } else if (e.type === 'round_revealed' && e.round_id === active?.id) {
        setReveal({
          correctAnswer: (e.correct_answer as string) ?? null,
          distribution: (e.distribution as Record<string, number>) ?? {},
          total: (e.total_submissions as number) ?? 0,
        })
        setActive((a) => (a ? { ...a, status: 'closed' } : a))
      }
    })
  }, [subscribe, sessionId, active?.id])

  const choose = (option: string) => {
    if (submitted || !active || active.status !== 'open' || reveal) return
    setSelected(option)
    if (send({ type: 'submit_answer', round_id: active.id, answer: option })) {
      setSubmitted(true)
    }
  }

  if (!active) {
    return (
      <section className="card btnpanel">
        <div className="op-label">🔘 보기 선택</div>
        <p className="muted">진행 중인 라운드가 없습니다. 운영자가 문제를 열면 시작됩니다.</p>
      </section>
    )
  }

  const options = active.options ?? ['1', '2', '3', '4']
  const myCorrect =
    reveal && reveal.correctAnswer != null && selected != null
      ? norm(selected) === norm(reveal.correctAnswer)
      : null

  return (
    <section className="card btnpanel">
      <div className="op-label">🔘 보기 선택</div>

      <div className="btnpanel-round">
        <strong>문제 {active.order_index}</strong>
        {active.prompt && <span className="muted"> · {active.prompt}</span>}
      </div>

      {/* 내 정답 여부 배너 (마감 후) */}
      {reveal && selected != null && (
        <p className={`btnpanel-verdict${myCorrect ? ' correct' : ' wrong'}`}>
          {myCorrect ? '⭕ 정답입니다!' : '❌ 오답입니다'}
        </p>
      )}
      {reveal && selected == null && (
        <p className="btnpanel-verdict muted">미제출</p>
      )}

      <div className="choice-grid">
        {options.map((opt, i) => {
          const isCorrect = reveal && reveal.correctAnswer != null && norm(reveal.correctAnswer) === norm(opt)
          const isMine = selected === opt
          const count = reveal?.distribution[opt] ?? 0
          return (
            <button
              key={`${opt}-${i}`}
              className={`choice${isMine ? ' mine' : ''}${
                reveal ? (isCorrect ? ' correct' : ' dim') : ''
              }`}
              disabled={submitted || !!reveal}
              onClick={() => choose(opt)}
            >
              <span className="choice-num">{i + 1}</span>
              <span className="choice-label">{opt}</span>
              {reveal && <span className="choice-count">{count}표</span>}
            </button>
          )
        })}
      </div>

      {reveal ? (
        <p className="btnpanel-status">
          정답: <strong>{reveal.correctAnswer ?? '—'}</strong> · 총 {reveal.total}명 제출
        </p>
      ) : submitted ? (
        <p className="btnpanel-status">제출 완료! 결과 공개를 기다리세요. ({progress}명 제출)</p>
      ) : (
        <p className="muted">하나를 선택하세요. ({progress}명 제출)</p>
      )}
    </section>
  )
}
