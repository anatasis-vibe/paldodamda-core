# PaldoDamdA OS

농수산물 도매 Master DB 기반 ERP Core 시스템

## 프로젝트 개요

PaldoDamdA OS는 팔도담다의 농수산물 위탁판매 운영을 위한 백엔드 시스템입니다.

- **Product Master DB**: 표준 상품 관리 (standard_products)
- **Import Engine**: 도매처 엑셀/HTML 파일 자동 파싱 및 매칭
- **FastAPI**: 검색 및 데이터 조회 API
- **Review Queue**: 미매칭 상품 관리

## 관련 프로젝트

- [palgo-damda](https://github.com/anatasis-vibe/palgo-damda) — 기존 소싱 캘린더 (독립 운영)
- 향후 palgo-damda에서 "PaldoDamdA OS 열기" 링크로 연결 예정

## 빠른 시작

```bash
# 1. 가상환경 생성
python -m venv .venv
.venv\Scripts\activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. DB 마이그레이션 (최초 1회)
python migrate.py

# 4. FastAPI 서버 실행
python -m uvicorn main:app --reload --port 8000

# API 문서
# http://localhost:8000/docs
```

## 디렉토리 구조

```
paldodamda-os/
├── main.py           # FastAPI 앱
├── migrate.py        # DB 마이그레이션
├── requirements.txt
├── engine/
│   ├── importer.py   # Import 오케스트레이터 (Transaction / History / Logging)
│   ├── normalizer.py # 속성 추출 (attribute_rules 기반)
│   ├── matcher.py    # 상품 매칭 (direct -> alias -> review_queue)
│   └── parser/       # HTML / XLSX / CSV 파서
├── scripts/
│   ├── ingest_all.py         # 원본 파일 일괄 파싱 (raw_items 적재)
│   └── normalize_product.py  # 상품 정규화 (product_offers 생성)
├── db/
│   └── schema.sql    # 전체 DB 스키마
├── data/
│   └── paldodamda.db # SQLite DB (git 제외)
├── docs/             # 설계 문서
├── logs/             # 일별 로그 (git 제외)
└── app/              # 향후 UI (Sprint 3+)
```

## Import Engine 파이프라인

```
파일 (XLSX / HTML / CSV)
    ↓ Parser      — 원본 그대로 ParsedRow 반환 (상품명 수정 없음)
    ↓ Normalizer  — attribute_rules 기반 속성 추출 (grade / weight / count / tag)
    ↓ Matcher     — standard_products → product_aliases → review_queue
    ↓ DB          — Transaction (실패 시 전체 Rollback)
```

## API 엔드포인트 (Sprint 1 구현)

- `GET /api/health` — 서버 상태 확인
- `GET /api/products?q=` — 상품 검색

## 개발 원칙 (CLAUDE.md)

- Product Master는 절대 자동 수정하지 않는다
- Alias는 검토 후에만 추가한다
- Rule Book은 Alias 검색 전에 실행한다
- 미매칭 상품은 Review Queue로 이동한다
- 모든 Import는 Rollback 가능해야 한다