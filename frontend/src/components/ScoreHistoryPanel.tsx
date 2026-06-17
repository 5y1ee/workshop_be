import { useCallback, useEffect, useState } from 'react'
import {
  api,
  ApiError,
  canEditScoreInState,
  type GameState,
  type ScoreLog,
} from '../api'
import { useLive } from '../live'

interface Props {
  token: string
  sessionId: number
  state: GameState
  subjectLabel: (type: string, id: number) => string
  onChanged: () => void
}

/** 운영자 전용: 세션에 부여된 점수 로그 목록 + 인라인 정정(수정). */
export default function ScoreHistoryPanel({
  token,
  sessionId,
  state,
  subjectLabel,
  onChanged,
}: Props) {
  const { lastEvent } = useLive()
  const [logs, setLogs] = useState<ScoreLog[]>([])
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editScore, setEditScore] = useState('0')
  const [editMemo, setEditMemo] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canEdit = canEditScoreInState(state)

  const load = useCallback(() => {
    api.scores(token, sessionId).then(setLogs).catch(() => setLogs([]))
  }, [token, sessionId])

  useEffect(load, [load])
  useEffect(() => {
    if (lastEvent?.type === 'score_recorded' && lastEvent.session_id === sessionId) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  const startEdit = (log: ScoreLog) => {
    setEditingId(log.id)
    setEditScore(String(log.score))
    setEditMemo(log.memo ?? '')
    setError(null)
  }

  const cancelEdit = () => {
    setEditingId(null)
    setError(null)
  }

  const save = async (log: ScoreLog) => {
    setBusy(true)
    setError(null)
    try {
      await api.updateScore(token, log.id, {
        score: Number(editScore) || 0,
        memo: editMemo.trim() === '' ? null : editMemo.trim(),
      })
      setEditingId(null)
      load()
      onChanged()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="op">
      <h3 className="section">🧾 점수 히스토리 (운영자)</h3>
      {!canEdit && (
        <p className="muted">진행중~종료(done) 상태에서 점수를 정정할 수 있습니다.</p>
      )}
      {logs.length === 0 ? (
        <p className="muted">아직 기록된 점수가 없습니다.</p>
      ) : (
        <ul className="score-history">
          {logs.map((log) => (
            <li key={log.id} className="score-history-row">
              <span className="sh-target">
                {log.subject_type === 'team' ? '🟦' : '👤'}{' '}
                {log.subject_name ?? subjectLabel(log.subject_type, log.subject_id)}
              </span>
              {editingId === log.id ? (
                <>
                  <input
                    className="op-score"
                    type="number"
                    value={editScore}
                    onChange={(e) => setEditScore(e.target.value)}
                  />
                  <input
                    className="sh-memo"
                    type="text"
                    placeholder="메모"
                    value={editMemo}
                    onChange={(e) => setEditMemo(e.target.value)}
                  />
                  <button className="op-btn" disabled={busy} onClick={() => save(log)}>
                    저장
                  </button>
                  <button className="op-btn ghost" disabled={busy} onClick={cancelEdit}>
                    취소
                  </button>
                </>
              ) : (
                <>
                  <span className="sh-score">{log.score}점</span>
                  {log.memo && <span className="muted sh-memo-text">{log.memo}</span>}
                  {log.updated_at && <span className="muted">· 수정됨</span>}
                  <button
                    className="op-btn"
                    disabled={!canEdit}
                    onClick={() => startEdit(log)}
                  >
                    수정
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  )
}
