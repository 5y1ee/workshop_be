import { useEffect, useState } from 'react'
import { useLive } from '../live'
import type { GameRound } from '../api'

interface RevealInfo {
  correctAnswer: string | null
  distribution: Record<string, number>
  total: number
}

interface Props {
  sessionId: number
  round: GameRound | null
}

/** input_type=button 게임용 보기 선택. 라운드별 1인 1답. */
export default function ButtonPanel({ sessionId, round }: Props) {
  const { send, subscribe } = useLive()
  const [selected, setSelected] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [progress, setProgress] = useState(0)
  const [reveal, setReveal] = useState<RevealInfo | null>(null)

  // 새 라운드가 열리면 상태 초기화
  useEffect(() => {
    setSelected(null)
    setSubmitted(false)
    setProgress(0)
    setReveal(null)
  }, [round?.id])

  useEffect(() => {
    return subscribe((e) => {
      if (e.session_id !== sessionId) return
      if (e.type === 'submission_progress') {
        setProgress(e.submitted as number)
      } else if (e.type === 'round_revealed') {
        setReveal({
          correctAnswer: (e.correct_answer as string) ?? null,
          distribution: (e.distribution as Record<string, number>) ?? {},
          total: (e.total_submissions as number) ?? 0,
        })
      }
    })
  }, [subscribe, sessionId])

  const choose = (option: string) => {
    if (submitted || !round) return
    setSelected(option)
    if (send({ type: 'submit_answer', round_id: round.id, answer: option })) {
      setSubmitted(true)
    }
  }

  const options = round?.options ?? ['1', '2', '3', '4']

  return (
    <section className="card btnpanel">
      <div className="op-label">🔘 보기 선택</div>

      {round ? (
        <>
          <div className="btnpanel-round">
            <strong>문제 {round.order_index}</strong>
            {round.prompt && <span className="muted"> · {round.prompt}</span>}
          </div>

          <div className="choice-grid">
            {options.map((opt, i) => {
              const isCorrect = reveal && reveal.correctAnswer === opt
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
        </>
      ) : (
        <p className="muted">진행 중인 라운드가 없습니다. 운영자가 문제를 열면 시작됩니다.</p>
      )}
    </section>
  )
}
