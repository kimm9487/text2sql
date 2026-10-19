import { useMemo, useState } from 'react'
import { formatValue } from '../../lib/format'
import type { Row } from '../../types'

const PAGE_SIZE = 20

// 결과 표 — 헤더 클릭 정렬 + 20행 페이지
export default function ResultTable({ columns, rows }: { columns: string[]; rows: Row[] }) {
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<{ col: string; asc: boolean } | null>(null)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const { col, asc } = sort
    return [...rows].sort((a, b) => {
      const x = a[col]
      const y = b[col]
      if (x === y) return 0
      if (x === null) return 1
      if (y === null) return -1
      const cmp = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'ko')
      return asc ? cmp : -cmp
    })
  }, [rows, sort])

  // 숫자 컬럼은 오른쪽 정렬, 회원ID 같은 식별자는 천 단위 쉼표 없이
  const numericCols = useMemo(
    () => new Set(columns.filter(c => rows.length > 0 && rows.every(r => r[c] === null || typeof r[c] === 'number'))),
    [columns, rows],
  )
  const isId = (c: string) => /id$/i.test(c)
  const cell = (c: string, v: Row[string]) => (isId(c) && typeof v === 'number' ? String(v) : formatValue(v))

  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const current = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const toggleSort = (col: string) => {
    setPage(0)
    setSort(s => (s?.col === col ? { col, asc: !s.asc } : { col, asc: false }))
  }

  return (
    <>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {columns.map(c => (
                <th key={c} onClick={() => toggleSort(c)} style={numericCols.has(c) ? { textAlign: 'right' } : undefined}>
                  {c}{sort?.col === c ? (sort.asc ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {current.map((r, i) => (
              <tr key={i}>
                {columns.map(c => (
                  <td key={c} className={numericCols.has(c) ? 'num' : ''}>{cell(c, r[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <span>{rows.length.toLocaleString()}행 중 {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, rows.length)}</span>
          <span style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>이전</button>
            <button className="btn btn-sm" disabled={page >= pages - 1} onClick={() => setPage(p => p + 1)}>다음</button>
          </span>
        </div>
      )}
    </>
  )
}
