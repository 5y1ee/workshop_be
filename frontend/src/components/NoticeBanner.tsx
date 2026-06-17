import { useEffect, useRef, useState } from 'react'
import { api, type Notice } from '../api'
import { useAuth } from '../auth'
import { useLive } from '../live'
import { useSeason } from '../season'

function isActive(notice: Notice | null): notice is Notice {
  return notice != null && new Date(notice.expires_at).getTime() > Date.now()
}

export default function NoticeBanner() {
  const { token } = useAuth()
  const { seasonId } = useSeason()
  const { subscribe } = useLive()
  const [notice, setNotice] = useState<Notice | null>(null)
  const [dismissedId, setDismissedId] = useState<number | null>(null)
  const [shouldScroll, setShouldScroll] = useState(false)
  const marqueeRef = useRef<HTMLDivElement>(null)
  const messageRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!token || seasonId == null) {
      setNotice(null)
      return
    }
    setDismissedId(null)
    api.currentNotice(token, seasonId)
      .then((res) => setNotice(isActive(res.notice) ? res.notice : null))
      .catch(() => setNotice(null))
  }, [token, seasonId])

  useEffect(() => {
    return subscribe((e) => {
      if (e.type === 'notice_created') {
        const next = e.notice as Notice | undefined
        if (!next || next.season_id !== seasonId) return
        setDismissedId(null)
        setNotice(isActive(next) ? next : null)
      }
      if (e.type === 'notice_deleted' && e.season_id === seasonId) {
        setNotice((prev) => (prev?.id === e.notice_id ? null : prev))
      }
    })
  }, [seasonId, subscribe])

  useEffect(() => {
    if (!notice) return
    const delay = new Date(notice.expires_at).getTime() - Date.now()
    if (delay <= 0) {
      setNotice(null)
      return
    }
    const timer = window.setTimeout(() => setNotice(null), delay)
    return () => window.clearTimeout(timer)
  }, [notice])

  useEffect(() => {
    const update = () => {
      const marquee = marqueeRef.current
      const message = messageRef.current
      setShouldScroll(Boolean(marquee && message && message.scrollWidth > marquee.clientWidth + 4))
    }
    update()

    const marquee = marqueeRef.current
    if (!marquee || typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', update)
      return () => window.removeEventListener('resize', update)
    }

    const observer = new ResizeObserver(update)
    observer.observe(marquee)
    return () => observer.disconnect()
  }, [notice?.message])

  if (!notice || notice.id === dismissedId) return null

  return (
    <div className="notice-banner">
      <span className="notice-kicker">공지</span>
      <div className={`notice-marquee${shouldScroll ? ' scrolling' : ''}`} ref={marqueeRef}>
        <span className="notice-message" ref={messageRef}>
          {notice.message}
        </span>
      </div>
      <button
        type="button"
        className="notice-dismiss"
        aria-label="공지 닫기"
        onClick={() => setDismissedId(notice.id)}
      >
        ×
      </button>
    </div>
  )
}
