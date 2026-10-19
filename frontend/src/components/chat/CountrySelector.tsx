import { COUNTRY_LABEL } from '../../lib/format'
import type { Country } from '../../types'

const OPTIONS: Country[] = ['ALL', 'KR', 'JP', 'TW']

export default function CountrySelector({ value, onChange }: { value: Country; onChange: (c: Country) => void }) {
  return (
    <div className="country-chips" role="radiogroup" aria-label="조회 국가">
      {OPTIONS.map(c => (
        <button
          key={c}
          type="button"
          role="radio"
          aria-checked={value === c}
          className={`country-chip ${value === c ? 'active' : ''}`}
          onClick={() => onChange(c)}
        >
          {c === 'ALL' ? '전체' : `${c} ${COUNTRY_LABEL[c]}`}
        </button>
      ))}
    </div>
  )
}
