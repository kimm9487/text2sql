import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

interface Props {
  disabled: boolean
  onSubmit: (q: string) => void
}

// Enter 전송 / Shift+Enter 줄바꿈, 내용에 맞춰 높이 자동 조절
export default function MessageInput({ disabled, onSubmit }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [text])

  const send = () => {
    const q = text.trim()
    if (!q || disabled) return
    onSubmit(q)
    setText('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="input-box">
      <textarea
        ref={ref}
        rows={1}
        value={text}
        maxLength={500}
        placeholder="예: 지난달 국가별 매출 알려줘"
        onChange={e => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <button className="btn btn-primary btn-sm" onClick={send} disabled={disabled || !text.trim()}>
        {disabled ? <span className="spinner" /> : '질문'}
      </button>
    </div>
  )
}
