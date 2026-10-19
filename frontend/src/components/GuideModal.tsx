import { useEffect, useState } from 'react'
import { getSchema } from '../lib/api'
import type { SchemaTable } from '../types'

// '조회 가능한 데이터' 안내 — 백엔드 schema_info 를 그대로 보여준다
export default function GuideModal({ onClose }: { onClose: () => void }) {
  const [tables, setTables] = useState<SchemaTable[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    getSchema().then(r => setTables(r.tables)).catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="card modal" onClick={e => e.stopPropagation()} role="dialog" aria-label="조회 가능한 데이터">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h2 style={{ flex: 1 }}>조회 가능한 데이터</h2>
          <button className="btn btn-sm" onClick={onClose}>닫기</button>
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          과제용 가상 웹소설 플랫폼 DB (2025-01 ~ 현재, 국가 KR/JP/TW). 실제 회사 데이터가 아닌 생성 데이터입니다.
          이름·이메일·전화번호는 결과에서 마스킹되고, 비밀번호 해시는 조회가 차단됩니다.
        </p>
        {error && <p className="auth-error">{error}</p>}
        {tables.map(t => (
          <div key={t.table} className="schema-table">
            <h3>{t.label} <span className="mono muted" style={{ fontSize: 12, fontWeight: 400 }}>{t.table}</span></h3>
            <div className="muted" style={{ fontSize: 12.5 }}>{t.description}</div>
            <ul>
              {t.columns.map(c => <li key={c.name}><span className="mono">{c.name}</span> — {c.description}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
