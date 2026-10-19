"""
차트 추천 + 요약 카드 — 결과 컬럼 형태를 보고 코드로 정한다 (LLM 미사용).

  - 첫 컬럼이 일자/월 → line
  - 라벨 1개 + 수치, 행 ≤ 8, 질문에 '비중/비율' → pie
  - 그 외 라벨 + 수치 → bar
  - 수치 컬럼이 없거나 1행이면 차트 없음 (요약 카드만)

TODO(기말): 요약 카드 아래에 LLM 이 쓰는 'AI 인사이트' 문장 추가 예정.
            숫자는 지금처럼 코드가 계산하고, LLM 은 설명만 쓰게 해서 숫자 환각을 막을 계획.
"""
from __future__ import annotations

_TIME_COLUMNS = ("일자", "월", "date", "month", "day")


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_id_column(name: str) -> bool:
    low = name.lower()
    return low.endswith("id") or low.endswith("_id")


def numeric_columns(columns: list[str], rows: list[dict]) -> list[str]:
    """지표로 쓸 수치 컬럼 (회원ID 같은 식별자는 숫자여도 제외)."""
    out = []
    for c in columns:
        if _is_id_column(c):
            continue
        values = [r.get(c) for r in rows if r.get(c) is not None]
        if values and all(_is_number(v) for v in values):
            out.append(c)
    return out


def recommend_chart(question: str, columns: list[str], rows: list[dict]) -> dict | None:
    """y 는 지표 후보 전체 — 화면에서 첫 번째를 기본으로 그리고 드롭다운으로 바꿀 수 있다."""
    if len(rows) < 2 or len(columns) < 2:
        return None
    nums = numeric_columns(columns, rows)
    labels = [c for c in columns if c not in nums and not _is_id_column(c)]
    if not nums or not labels:
        return None

    x = labels[0]
    if x.lower() in _TIME_COLUMNS:
        # 시간축 + 다른 라벨(예: 국가)이 있으면 라벨별로 선을 나눠 그린다
        series = labels[1] if len(labels) > 1 else None
        return {"type": "line", "x": x, "y": nums, "series": series}
    if len(rows) <= 8 and any(k in question for k in ("비중", "비율", "점유")):
        return {"type": "pie", "x": x, "y": nums, "series": None}
    return {"type": "bar", "x": x, "y": nums, "series": None}


def summary_cards(columns: list[str], rows: list[dict]) -> list[dict]:
    """1행이면 각 수치를 카드로, 여러 행이면 첫 수치 컬럼의 합계·최대 항목을 카드로."""
    if not rows:
        return []
    nums = numeric_columns(columns, rows)
    if not nums:
        return [{"label": "조회 건수", "value": len(rows), "unit": "행"}]
    if len(rows) == 1:
        return [{"label": c, "value": rows[0][c], "unit": ""} for c in nums[:4]]

    main = nums[0]
    labels = [c for c in columns if c not in nums]
    total = sum(r.get(main) or 0 for r in rows)
    cards = [{"label": f"{main} 합계", "value": total, "unit": ""}]
    if labels:
        top = max(rows, key=lambda r: r.get(main) or 0)
        low = min(rows, key=lambda r: r.get(main) or 0)
        cards.append({"label": f"최대 ({top.get(labels[0])})", "value": top.get(main), "unit": ""})
        cards.append({"label": f"최소 ({low.get(labels[0])})", "value": low.get(main), "unit": ""})
    cards.append({"label": "행 수", "value": len(rows), "unit": "행"})
    return cards
