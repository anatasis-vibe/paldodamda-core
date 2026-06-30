# PaldoDamdA OS — Roadmap

## Phase 1 (현재) — 로컬 웹앱 v1

- [x] Import Engine (Parser / Normalizer / Matcher / Transaction)
- [x] SQLite DB (standard_products / product_offers / review_queue / import_history / price_history)
- [x] FastAPI (상품 검색 / 가격 비교 / Review Queue API)
- [x] Streamlit UI (상품 검색 / 가격 비교 / Review Queue 승인 / Import / 이력)

## Phase 2 — 자동화 + 외부 연동

- [ ] Google Sheets 링크 입력
- [ ] 주기적 가격표 체크 (cron / 스케줄러)
- [ ] 변경된 가격 자동 감지 + Import History 기록
- [ ] 도매처 URL 저장 및 크롤링 연동

## Phase 3 — 검색 고도화

- [ ] Fuzzy 매칭 (rapidfuzz)
- [ ] AI 기반 상품 자동 매칭 (LLM alias 제안)
- [ ] Review Queue 일괄 승인
- [ ] 상품 패밀리 계층 구조 (family / subcategory)

## Phase 4 — 웹 배포

- [ ] Next.js 프론트엔드
- [ ] Vercel 배포
- [ ] 로그인 (간단한 팀 인증)
- [ ] palgo-damda 소싱캘린더에 "PaldoDamdA OS 열기" 링크 추가

## Phase 5 — ERP 확장

- [ ] 발주서 생성
- [ ] 도매처별 마감일 관리
- [ ] 출하 스케줄 캘린더
- [ ] PostgreSQL 전환
