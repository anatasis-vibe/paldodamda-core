# Matching Engine

## 매칭 순서

1. **Direct Match** — standard_products.standard_name == product_name (confidence 1.0)
2. **Alias Match** — product_aliases.alias == product_name (confidence 0.9)
3. **No Match** → review_queue 저장 (confidence 0.0)

## product_name 결정 방식

Normalizer가 original_name에서 속성 키워드(등급, 중량, 과수, 태그 등)를 제거한 후 남은 텍스트.

예시:
```
original_name: "신비복숭아 특품 2kg 8과"
→ grade=특품, weight=2kg, count=8과 제거
→ product_name: "신비복숭아"
→ Matcher: standard_products에서 "신비복숭아" 직접 매칭 (confidence 1.0)
```

## Review Queue 승인 흐름 (Sprint 3 예정)

1. GET /api/review — 미매칭 목록 확인
2. 검토 후 alias 추가 OR 새 standard_product 추가
3. POST /api/review/approve — 승인 처리

## 원칙

- Matcher는 Product Master를 수정하지 않는다
- 새 Alias는 검토 후에만 추가한다 (Never auto-approve)
- AI 자동 매칭은 Sprint 4 이후 도입