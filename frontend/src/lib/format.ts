const nf = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1 })

export function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '-'
  if (typeof v === 'number') return nf.format(v)
  return String(v)
}

export const COUNTRY_LABEL: Record<string, string> = {
  ALL: '전체',
  KR: '한국',
  JP: '일본',
  TW: '대만',
}

export function formatTime(ts: number): string {
  return new Intl.DateTimeFormat('ko-KR', { hour: '2-digit', minute: '2-digit' }).format(new Date(ts))
}
