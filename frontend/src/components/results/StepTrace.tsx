import type { Step } from '../../types'

// 워크시트의 처리 흐름 순서 — 실행되지 않은 단계는 회색으로 표시
const ALL_STEPS: { key: string; label: string }[] = [
  { key: 'filter', label: '입력 필터' },
  { key: 'intent', label: '의도 분류' },
  { key: 'period', label: '기간 해석' },
  { key: 'generate', label: 'SQL 생성' },
  { key: 'validate', label: 'SQL 검증' },
  { key: 'execute', label: '읽기전용 실행' },
  { key: 'mask', label: '결과 마스킹' },
  { key: 'chart', label: '차트 추천' },
]

const ICON: Record<string, string> = { ok: '✓', info: 'i', blocked: '✕', error: '!', skipped: '' }

export default function StepTrace({ steps, chat }: { steps: Step[]; chat: boolean }) {
  const done = new Map(steps.map(s => [s.key, s]))
  const visible = chat ? steps : ALL_STEPS.map(s => done.get(s.key) ?? { ...s, status: 'skipped', detail: '실행 안 함', ms: 0 })

  return (
    <ol className="steps">
      {visible.map((s, i) => (
        <li key={`${s.key}-${i}`} className="step">
          <span className={`step-dot ${s.status}`}>{ICON[s.status]}</span>
          <div className="step-body">
            <div className="name">{s.label}</div>
            <div className="detail">
              {s.detail}
              {s.status !== 'skipped' && s.ms > 0 && <span> · {s.ms.toLocaleString()}ms</span>}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
