# PaldoDamdA OS — Roadmap

## Phase 1 (완료) — 로컬 웹앱 v1

- [x] Import Engine (Parser / Normalizer / Matcher / Transaction)
- [x] SQLite DB (standard_products / product_offers / review_queue / import_history / price_history)
- [x] FastAPI (상품 검색 / 가격 비교 / Review Queue API)
- [x] Streamlit UI (상품 검색 / 가격 비교 / 검수 필요 / 가격표 업데이트 / 이력)
- [x] product_offers.product_url 컬럼 추가 (Phase 2 준비)

## Phase 2 — 자동화 + 외부 연동

- [ ] 도매처 Google Sheets URL 등록 (product_url 활용)
- [ ] Google Sheets 자동 체크 (주기적 폴링)
- [ ] 가격 변경 감지 → 자동 Import
- [ ] 도매처 상품 URL 저장 ("주문하기" 버튼 준비)
- [ ] 설정 탭: 도매처 관리 (URL, 연락처, 마감일)

## Phase 3 — 검색 고도화

- [ ] Fuzzy 매칭 (rapidfuzz) — 오타·유사 상품명 허용
- [ ] AI 기반 상품 자동 매칭 (LLM alias 제안)
- [ ] 검수 필요 일괄 승인 (CSV 업로드)
- [ ] 상품 패밀리 계층 구조 (family / subcategory)
- [ ] 카테고리별 시세 대시보드

## Phase 4 — 주문 워크플로우

- [ ] "주문하기" 버튼 (도매처 URL 연결)
- [ ] 발주서 자동 생성 (PDF/엑셀)
- [ ] 도매처별 주문 마감일 알림
- [ ] 출하 스케줄 캘린더

## Phase 5 — 웹 배포

- [ ] Next.js 프론트엔드
- [ ] Vercel 배포
- [ ] 팀 로그인 (간단한 인증)
- [ ] palgo-damda 소싱캘린더에 "PaldoDamdA OS 열기" 링크 추가
- [ ] PostgreSQL 전환 (대용량 데이터 대비)
