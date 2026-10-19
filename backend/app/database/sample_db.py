"""
과제용 샘플 DB 생성 스크립트 (SQLite)

가상의 웹소설 플랫폼 데이터를 만든다. 실제 회사 DB 대신 시연·과제 제출용으로 쓰기 위한 것이라
모든 이름·이메일·전화번호는 임의 생성값이고, 이메일 도메인은 예약 도메인(example.*)만 쓴다.

- 기간: 2025-01-01 ~ 생성일(기본 오늘). "이번달/지난달" 질문에 항상 데이터가 있도록 끝날짜를 오늘로 둔다.
- 국가: KR / JP / TW (워크시트의 '국가 선택' 기능 시연용)
- 같은 시드(학번)로 생성하므로 끝날짜가 같으면 항상 같은 데이터가 나온다.

서버를 처음 켤 때 DB 파일이 없으면 자동으로 생성된다 (main.py lifespan).
직접 다시 만들 때는 scripts/seed_db.py 를 쓴다:
    python scripts/seed_db.py            # data/content_platform.db 가 없을 때만 생성
    python scripts/seed_db.py --reset    # 기존 파일 지우고 다시 생성
    python scripts/seed_db.py --end-date 2026-10-31
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from app.config import settings

DEFAULT_DB_PATH = settings.db_file

SEED = 20222103
START_DATE = date(2025, 1, 1)
COIN_TO_KRW = 100  # 코인 1개 = 100원 (파트너 매출 계산 기준)

SCHEMA_SQL = """
-- 콘텐츠 제공 파트너사(CP)
CREATE TABLE partners (
    partner_id     INTEGER PRIMARY KEY,
    partner_name   TEXT NOT NULL,          -- 업체명
    country        TEXT NOT NULL,          -- 업체 소속 국가 (KR/JP/TW)
    contract_type  TEXT NOT NULL,          -- exclusive(독점) / non_exclusive(비독점)
    revenue_share  REAL NOT NULL,          -- 정산 비율 (0.5 = 50%)
    contact_email  TEXT,                   -- 담당자 이메일
    joined_at      DATE NOT NULL           -- 계약 시작일
);

-- 작가
CREATE TABLE authors (
    author_id   INTEGER PRIMARY KEY,
    pen_name    TEXT NOT NULL,             -- 필명
    partner_id  INTEGER NOT NULL REFERENCES partners(partner_id)
);

-- 작품
CREATE TABLE contents (
    content_id          INTEGER PRIMARY KEY,
    title               TEXT NOT NULL,     -- 작품명
    genre               TEXT NOT NULL,     -- 장르
    author_id           INTEGER NOT NULL REFERENCES authors(author_id),
    partner_id          INTEGER NOT NULL REFERENCES partners(partner_id),
    price_per_episode   INTEGER NOT NULL,  -- 회차당 코인
    total_episodes      INTEGER NOT NULL,  -- 총 회차 수
    is_completed        INTEGER NOT NULL,  -- 완결 여부 (1=완결)
    released_at         DATE NOT NULL      -- 연재 시작일
);

-- 회원 (개인정보 포함 — 조회 시 마스킹/차단 대상)
CREATE TABLE members (
    member_id       INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,         -- 민감 컬럼: SQL 검증기가 조회 차단
    country         TEXT NOT NULL,         -- KR/JP/TW
    gender          TEXT NOT NULL,         -- M/F
    birth_year      INTEGER NOT NULL,
    signup_channel  TEXT NOT NULL,         -- organic/google/kakao/line/apple/ad
    status          TEXT NOT NULL,         -- active/dormant/withdrawn
    joined_at       DATETIME NOT NULL,     -- 가입일시
    last_login_at   DATETIME,              -- 마지막 로그인
    withdrawn_at    DATETIME               -- 탈퇴일시 (탈퇴 회원만)
);

-- 코인 충전 결제 (플랫폼 매출의 기준)
CREATE TABLE payments (
    payment_id  INTEGER PRIMARY KEY,
    member_id   INTEGER NOT NULL REFERENCES members(member_id),
    country     TEXT NOT NULL,
    amount      INTEGER NOT NULL,          -- 결제 금액 (원 환산)
    coins       INTEGER NOT NULL,          -- 지급 코인
    method      TEXT NOT NULL,             -- card/mobile/easy_pay/in_app
    status      TEXT NOT NULL,             -- paid(완료)/refunded(환불)
    paid_at     DATETIME NOT NULL
);

-- 코인 사용 (작품 회차 구매 — 파트너사·작품 매출의 기준)
CREATE TABLE coin_usages (
    usage_id    INTEGER PRIMARY KEY,
    member_id   INTEGER NOT NULL REFERENCES members(member_id),
    content_id  INTEGER NOT NULL REFERENCES contents(content_id),
    country     TEXT NOT NULL,
    episodes    INTEGER NOT NULL,          -- 구매 회차 수
    coins       INTEGER NOT NULL,          -- 사용 코인
    used_at     DATETIME NOT NULL
);

-- 로그인 기록 (DAU/MAU 계산용)
CREATE TABLE login_logs (
    log_id     INTEGER PRIMARY KEY,
    member_id  INTEGER NOT NULL REFERENCES members(member_id),
    country    TEXT NOT NULL,
    device     TEXT NOT NULL,              -- android/ios/web
    login_at   DATETIME NOT NULL
);

CREATE INDEX idx_members_joined ON members(joined_at);
CREATE INDEX idx_members_withdrawn ON members(withdrawn_at);
CREATE INDEX idx_payments_paid ON payments(paid_at);
CREATE INDEX idx_payments_member ON payments(member_id);
CREATE INDEX idx_usages_used ON coin_usages(used_at);
CREATE INDEX idx_usages_content ON coin_usages(content_id);
CREATE INDEX idx_logins_login ON login_logs(login_at);
CREATE INDEX idx_logins_member ON login_logs(member_id);
"""

# ── 이름 재료 (전부 임의 조합) ──────────────────────────────────────────────
PARTNER_NAMES = [
    ("가람 스튜디오", "KR"), ("누리 픽션", "KR"), ("다온 미디어", "KR"), ("라온 북스", "KR"),
    ("마루 콘텐츠", "KR"), ("바른 스토리", "KR"), ("새봄 문고", "KR"), ("아라 엔터", "KR"),
    ("자람 북스", "KR"), ("초록 펜", "KR"), ("큰별 스튜디오", "KR"), ("파랑 서재", "KR"),
    ("하늘 문고", "KR"), ("Sakura Works", "JP"), ("Momiji Books", "JP"), ("Hoshizora Press", "JP"),
    ("Yushan Media", "TW"), ("Formosa Story", "TW"), ("Blue Fox Studio", "TW"), ("Night Owl Press", "JP"),
]

GENRES = ["로맨스", "판타지", "로맨스판타지", "무협", "현대판타지", "드라마", "미스터리", "코미디"]
GENRE_WEIGHTS = [0.22, 0.18, 0.18, 0.08, 0.16, 0.08, 0.06, 0.04]

TITLE_A = ["검은 달의", "회귀한", "마지막", "잊혀진", "푸른", "황금빛", "비밀스러운", "열두 번째",
           "은빛", "붉은", "몰락한", "다시 태어난", "이름 없는", "새벽의", "겨울의", "환생한"]
TITLE_B = ["기사", "마법사", "공녀", "검객", "황제", "정원사", "탐정", "용병", "후계자",
           "약혼자", "연금술사", "사냥꾼", "계약 결혼", "도서관", "왕관", "편지"]

PEN_A = ["달빛", "윤슬", "새벽", "하람", "가온", "다솜", "미르", "별하", "누리", "소담", "한결", "여름"]
PEN_B = ["작가", "글", "서", "책방", "펜", "노트", "이야기", "공방"]

KR_LAST = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오"]
KR_FIRST = ["민준", "서연", "도윤", "지우", "하준", "서윤", "예준", "하은", "지호", "수아", "준서", "지민"]
JP_LAST = ["Sato", "Suzuki", "Takahashi", "Tanaka", "Ito", "Watanabe", "Yamamoto", "Nakamura"]
JP_FIRST = ["Yui", "Haruto", "Sora", "Riko", "Ren", "Mei", "Yuto", "Hina"]
TW_LAST = ["Chen", "Lin", "Huang", "Chang", "Lee", "Wang", "Wu", "Liu"]
TW_FIRST = ["Wei", "Yu", "Ting", "Hao", "Xin", "Jie", "Han", "Yi"]

COUNTRY_WEIGHTS = {"KR": 0.55, "JP": 0.30, "TW": 0.15}
PACKAGES = [(1000, 0.15), (3000, 0.25), (5000, 0.25), (10000, 0.20), (30000, 0.10), (50000, 0.05)]
METHODS = {
    "KR": (["card", "mobile", "easy_pay", "in_app"], [0.40, 0.20, 0.25, 0.15]),
    "JP": (["card", "mobile", "easy_pay", "in_app"], [0.35, 0.25, 0.10, 0.30]),
    "TW": (["card", "mobile", "easy_pay", "in_app"], [0.30, 0.15, 0.30, 0.25]),
}


def _weighted(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _day_weight(d: date, start: date, end: date) -> float:
    """일자별 활동 가중치 — 완만한 성장 추세 + 주말 가산 + 월별 변동."""
    span = max((end - start).days, 1)
    trend = 0.6 + 0.8 * (d - start).days / span
    weekend = 1.15 if d.weekday() >= 5 else 1.0
    month_wave = 1.0 + 0.12 * ((d.month * 7) % 5 - 2) / 2  # 달마다 조금씩 다르게
    return trend * weekend * month_wave


def _random_time(rng: random.Random, d: date) -> datetime:
    """저녁 시간대(20~23시)에 몰리는 시각 분포."""
    hour = _weighted(rng, list(range(24)),
                     [1, 1, 1, 1, 1, 1, 2, 3, 4, 4, 4, 5, 6, 5, 5, 5, 5, 6, 7, 8, 10, 11, 10, 5])
    return datetime(d.year, d.month, d.day, hour, rng.randint(0, 59), rng.randint(0, 59))


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _make_name(rng: random.Random, country: str) -> str:
    if country == "KR":
        return rng.choice(KR_LAST) + rng.choice(KR_FIRST)
    if country == "JP":
        return f"{rng.choice(JP_LAST)} {rng.choice(JP_FIRST)}"
    return f"{rng.choice(TW_LAST)} {rng.choice(TW_FIRST)}"


def _make_phone(rng: random.Random, country: str) -> str:
    if country == "KR":
        return f"010-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
    if country == "JP":
        return f"0{rng.choice([7, 8, 9])}0-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
    return f"09{rng.randint(10, 99)}-{rng.randint(100, 999)}-{rng.randint(100, 999)}"


def build(db_path: Path, end_date: date) -> dict[str, int]:
    rng = random.Random(SEED)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)

    all_days = [START_DATE + timedelta(days=i) for i in range((end_date - START_DATE).days + 1)]
    day_weights = [_day_weight(d, START_DATE, end_date) for d in all_days]

    # ── 파트너사 / 작가 / 작품 ──────────────────────────────────────────
    partners = []
    for pid, (name, country) in enumerate(PARTNER_NAMES, start=1):
        partners.append((
            pid, name, country,
            "exclusive" if rng.random() < 0.4 else "non_exclusive",
            rng.choice([0.5, 0.55, 0.6, 0.65, 0.7]),
            f"cp{pid:02d}@example.org",
            (date(2023, 1, 1) + timedelta(days=rng.randint(0, 700))).isoformat(),
        ))
    conn.executemany("INSERT INTO partners VALUES (?,?,?,?,?,?,?)", partners)

    # 업체마다 규모 차이를 둬서 '매출 하위 업체' 질문이 의미 있게 나오도록 한다.
    partner_size = {p[0]: rng.choice([1, 1, 2, 3, 4, 6]) for p in partners}
    authors = []
    used_pen = set()
    for aid in range(1, 81):
        while True:
            pen = rng.choice(PEN_A) + rng.choice(PEN_B)
            if pen not in used_pen:
                break
            pen = f"{pen}{aid}"
            if pen not in used_pen:
                break
        used_pen.add(pen)
        # 앞쪽 작가는 업체마다 1명씩 배정해 작가 없는 업체가 생기지 않게 한다
        if aid <= len(partners):
            pid = aid
        else:
            pid = _weighted(rng, list(partner_size), list(partner_size.values()))
        authors.append((aid, pen, pid))
    conn.executemany("INSERT INTO authors VALUES (?,?,?)", authors)

    contents = []
    used_titles = set()
    for cid in range(1, 151):
        while True:
            title = f"{rng.choice(TITLE_A)} {rng.choice(TITLE_B)}"
            if title not in used_titles:
                break
        used_titles.add(title)
        # 앞쪽 작품은 업체별 대표 작가에게 배정 → 모든 업체가 작품을 1개 이상 가진다
        aid, _, pid = authors[cid - 1] if cid <= len(partners) else rng.choice(authors)
        released = START_DATE - timedelta(days=400) + timedelta(days=rng.randint(0, 400 + (end_date - START_DATE).days - 30))
        contents.append((
            cid, title, _weighted(rng, GENRES, GENRE_WEIGHTS), aid, pid,
            rng.choice([2, 3, 3, 4, 5]), rng.randint(40, 300), 1 if rng.random() < 0.35 else 0,
            released.isoformat(),
        ))
    conn.executemany("INSERT INTO contents VALUES (?,?,?,?,?,?,?,?,?)", contents)

    # 작품 인기도: 지프 분포(소수 인기작에 매출 집중) × 업체 규모
    order = list(range(len(contents)))
    rng.shuffle(order)
    popularity = [0.0] * len(contents)
    for rank, idx in enumerate(order, start=1):
        popularity[idx] = (1 / rank ** 0.9) * (0.6 + 0.1 * partner_size[contents[idx][4]])
    content_ids = [c[0] for c in contents]
    content_genre = {c[0]: c[2] for c in contents}
    content_price = {c[0]: c[5] for c in contents}
    content_release = {c[0]: date.fromisoformat(c[8]) for c in contents}
    # 선호 장르 작품은 2.5배 더 자주 고르도록 장르별 가중치를 미리 계산
    genre_weights = {
        g: [popularity[i] * (2.5 if content_genre[c] == g else 1.0) for i, c in enumerate(content_ids)]
        for g in GENRES
    }

    # ── 회원 + 로그인/결제/코인사용 ────────────────────────────────────────
    members, logins, payments, usages = [], [], [], []
    countries = list(COUNTRY_WEIGHTS)
    cweights = list(COUNTRY_WEIGHTS.values())

    for mid in range(1, 5001):
        country = _weighted(rng, countries, cweights)
        join_day = _weighted(rng, all_days, day_weights)
        joined_at = _random_time(rng, join_day)
        channel_social = "kakao" if country == "KR" else "line"
        channel = _weighted(rng, ["organic", "google", channel_social, "apple", "ad"], [0.35, 0.2, 0.2, 0.1, 0.15])

        # 이용 기간: 절반은 일정 기간 뒤 이탈(로그인 중단), 7%는 탈퇴
        remain_days = (end_date - join_day).days
        if rng.random() < 0.5:
            active_days = min(remain_days, int(rng.expovariate(1 / 90)))
        else:
            active_days = remain_days
        withdrawn_at = None
        if rng.random() < 0.07 and remain_days > 3:
            wd = join_day + timedelta(days=rng.randint(1, max(1, min(remain_days, active_days + 30))))
            if wd <= end_date:
                withdrawn_at = _random_time(rng, wd)
                active_days = min(active_days, (wd - join_day).days)

        login_rate = rng.uniform(0.02, 0.22)
        device_main = _weighted(rng, ["android", "ios", "web"], [0.5, 0.3, 0.2])
        member_logins = []
        for offset in range(active_days + 1):
            if offset == 0 or rng.random() < login_rate:
                d = join_day + timedelta(days=offset)
                dev = device_main if rng.random() < 0.85 else rng.choice(["android", "ios", "web"])
                t = joined_at + timedelta(minutes=1) if offset == 0 else _random_time(rng, d)
                member_logins.append((mid, country, dev, _fmt(t)))
        logins.extend(member_logins)
        last_login = max(member_logins, key=lambda r: r[3])[3] if member_logins else None

        if withdrawn_at:
            status = "withdrawn"
        elif last_login and datetime.fromisoformat(last_login).date() < end_date - timedelta(days=180):
            status = "dormant"
        else:
            status = "active"

        members.append((
            mid, _make_name(rng, country),
            f"user{mid:04d}@" + rng.choice(["example.com", "example.net", "example.org"]),
            _make_phone(rng, country),
            hashlib.sha256(f"fake-{mid}-{rng.random()}".encode()).hexdigest(),
            country, rng.choice(["M", "F"]),
            int(rng.triangular(1965, 2008, 1995)),
            channel, status, _fmt(joined_at), last_login, _fmt(withdrawn_at),
        ))

        # 결제: 회원의 약 32%만 결제, 그중 일부는 헤비 결제자
        roll = rng.random()
        if roll > 0.32 or active_days < 1:
            continue
        interval = 12 if roll < 0.04 else 40
        n_pay = max(1, int(rng.expovariate(1 / max(1, active_days / interval))))
        n_pay = min(n_pay, 40)
        fav_genre = _weighted(rng, GENRES, GENRE_WEIGHTS)
        methods, mweights = METHODS[country]
        method_main = _weighted(rng, methods, mweights)

        for _ in range(n_pay):
            pay_day = join_day + timedelta(days=rng.randint(0, active_days))
            amount = _weighted(rng, [p[0] for p in PACKAGES], [p[1] for p in PACKAGES])
            bonus = 1.15 if amount >= 50000 else 1.10 if amount >= 30000 else 1.05 if amount >= 10000 else 1.0
            coins = int(amount // COIN_TO_KRW * bonus)
            status_pay = "refunded" if rng.random() < 0.04 else "paid"
            method = method_main if rng.random() < 0.8 else rng.choice(methods)
            paid_at = _random_time(rng, pay_day)
            payments.append((mid, country, amount, coins, method, status_pay, _fmt(paid_at)))
            if status_pay != "paid":
                continue

            # 충전한 코인을 이후 며칠에 걸쳐 작품 회차 구매에 사용
            left = coins
            while left > 0:
                cid = _weighted(rng, content_ids, genre_weights[fav_genre])
                use_day = pay_day + timedelta(days=rng.randint(0, 20))
                if use_day > end_date:
                    use_day = end_date
                if use_day < content_release[cid]:
                    continue
                price = content_price[cid]
                eps = min(rng.randint(1, 10), max(1, left // price))
                cost = eps * price
                if cost > left:
                    break
                left -= cost
                used_at = max(_random_time(rng, use_day), paid_at + timedelta(minutes=1))
                usages.append((mid, cid, country, eps, cost, _fmt(used_at)))

    conn.executemany("INSERT INTO members VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", members)
    payments.sort(key=lambda r: r[6])
    conn.executemany(
        "INSERT INTO payments (member_id,country,amount,coins,method,status,paid_at) VALUES (?,?,?,?,?,?,?)",
        payments,
    )
    usages.sort(key=lambda r: r[5])
    conn.executemany(
        "INSERT INTO coin_usages (member_id,content_id,country,episodes,coins,used_at) VALUES (?,?,?,?,?,?)",
        usages,
    )
    logins.sort(key=lambda r: r[3])
    conn.executemany("INSERT INTO login_logs (member_id,country,device,login_at) VALUES (?,?,?,?)", logins)
    conn.commit()

    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ["partners", "authors", "contents", "members", "payments", "coin_usages", "login_logs"]
    }
    conn.execute("VACUUM")
    conn.close()
    return counts


def ensure_db(db_path: Path = DEFAULT_DB_PATH, end_date: date | None = None) -> bool:
    """DB 파일이 없으면 생성한다. 새로 만들었으면 True."""
    if db_path.exists():
        return False
    build(db_path, end_date or date.today())
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="과제용 샘플 DB 생성")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--reset", action="store_true", help="기존 DB 삭제 후 재생성")
    parser.add_argument("--end-date", type=date.fromisoformat, default=None, help="데이터 끝날짜 (기본 오늘)")
    args = parser.parse_args()

    if args.db.exists():
        if not args.reset:
            print(f"이미 존재함: {args.db} (다시 만들려면 --reset)")
            return 0
        args.db.unlink()

    end_date = args.end_date or date.today()
    counts = build(args.db, end_date)
    print(f"생성 완료: {args.db}  (기간 {START_DATE} ~ {end_date})")
    for table, n in counts.items():
        print(f"  {table:<12} {n:>8,}행")
    return 0

