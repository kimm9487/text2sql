import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ChartSpec, Row } from '../../types'

const PALETTE = ['#2563eb', '#14b8a6', '#b06b00', '#7c3aed', '#c2402a', '#0891b2', '#db2777', '#4b5563']
const COUNTRY_COLOR: Record<string, string> = { KR: '#2563eb', JP: '#c2402a', TW: '#109362' }
const MAX_BAR_ITEMS = 30 // 항목이 너무 많으면 축 라벨이 뭉개져서 상위 30개만 그림 (시계열은 전부)

const nf = new Intl.NumberFormat('ko-KR')

function buildOption(spec: ChartSpec, rows: Row[], metric: string) {
  const base = {
    color: PALETTE,
    tooltip: { trigger: spec.type === 'pie' ? 'item' : 'axis', valueFormatter: (v: number) => nf.format(v) },
    grid: { left: 12, right: 36, top: 36, bottom: 12, containLabel: true },
    textStyle: { fontFamily: 'Pretendard Variable, Pretendard, sans-serif' },
  }

  if (spec.type === 'pie') {
    return {
      ...base,
      legend: { bottom: 0, type: 'scroll' },
      series: [{
        type: 'pie', radius: ['40%', '68%'], center: ['50%', '45%'],
        label: { formatter: '{b}\n{d}%' },
        data: rows.map(r => ({ name: String(r[spec.x]), value: Number(r[metric] ?? 0) })),
      }],
    }
  }

  if (spec.type === 'line') {
    const xs = Array.from(new Set(rows.map(r => String(r[spec.x]))))
    if (spec.series) {
      // 예: 월 × 국가 → 국가별 선
      const groups = Array.from(new Set(rows.map(r => String(r[spec.series!]))))
      return {
        ...base,
        legend: { top: 0 },
        xAxis: { type: 'category', data: xs, boundaryGap: false },
        yAxis: { type: 'value', axisLabel: { formatter: (v: number) => nf.format(v) } },
        series: groups.map(g => ({
          name: g, type: 'line', smooth: true, showSymbol: xs.length <= 31,
          itemStyle: COUNTRY_COLOR[g] ? { color: COUNTRY_COLOR[g] } : undefined,
          data: xs.map(x => {
            const hit = rows.find(r => String(r[spec.x]) === x && String(r[spec.series!]) === g)
            return hit ? Number(hit[metric] ?? 0) : null
          }),
        })),
      }
    }
    return {
      ...base,
      xAxis: { type: 'category', data: xs, boundaryGap: false },
      yAxis: { type: 'value', axisLabel: { formatter: (v: number) => nf.format(v) } },
      series: [{
        name: metric, type: 'line', smooth: true, showSymbol: xs.length <= 31, areaStyle: { opacity: 0.08 },
        data: rows.map(r => Number(r[metric] ?? 0)),
      }],
    }
  }

  const items = rows.slice(0, MAX_BAR_ITEMS)
  const labels = items.map(r => String(r[spec.x]))
  const longLabels = labels.some(l => l.length > 6) || labels.length > 8
  return {
    ...base,
    xAxis: {
      type: 'category', data: labels,
      axisLabel: { interval: 0, rotate: longLabels ? 30 : 0, width: 90, overflow: 'truncate' },
    },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => nf.format(v) } },
    series: [{
      name: metric, type: 'bar', barMaxWidth: 42,
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      data: items.map(r => {
        const label = String(r[spec.x])
        return COUNTRY_COLOR[label]
          ? { value: Number(r[metric] ?? 0), itemStyle: { color: COUNTRY_COLOR[label] } }
          : Number(r[metric] ?? 0)
      }),
    }],
  }
}

export default function ChartView({ spec, rows }: { spec: ChartSpec; rows: Row[] }) {
  const [metric, setMetric] = useState(spec.y[0])

  useEffect(() => setMetric(spec.y[0]), [spec])

  const option = useMemo(() => buildOption(spec, rows, metric), [spec, rows, metric])
  const truncated = spec.type === 'bar' && rows.length > MAX_BAR_ITEMS

  return (
    <div>
      <div className="chart-toolbar">
        <span className="badge">{spec.type === 'line' ? '선 그래프' : spec.type === 'pie' ? '원 그래프' : '막대 그래프'}</span>
        {spec.y.length > 1 && (
          <label>
            지표{' '}
            <select value={metric} onChange={e => setMetric(e.target.value)}>
              {spec.y.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </label>
        )}
        {truncated && <span className="muted">항목이 많아 상위 {MAX_BAR_ITEMS}개만 표시</span>}
      </div>
      <div className="card chart-card">
        <ReactECharts option={option} notMerge style={{ height: 360 }} />
      </div>
    </div>
  )
}
