# API Spec — PaldoDamdA OS v0.3.0

Base URL (local): `http://localhost:8000`
Docs: `http://localhost:8000/docs`

---

## System

### GET /api/health

서버 상태 및 핵심 테이블 row 수 반환.

**Response**
```json
{
  "status": "ok",
  "standard_products": 28,
  "product_aliases": 10,
  "product_offers": 16945,
  "review_queue_pending": 254,
  "import_history_count": 3
}
```

---

## Products

### GET /api/products

상품 검색. 상품명 + alias 동시 검색. 카테고리 필터 지원.

**Query Parameters**

| param    | type   | default | description           |
|----------|--------|---------|----------------------|
| q        | string | ""      | 상품명 또는 alias 검색어 |
| category | string | ""      | 카테고리 필터 (과일 / 농산물) |

**Response**
```json
{
  "q": "복숭아",
  "category": "",
  "count": 6,
  "products": [
    {
      "id": 7,
      "standard_name": "신비복숭아",
      "category": "과일",
      "offer_count": 169,
      "min_price": 8000,
      "max_price": 52000,
      "suppliers": "공급사A,공급사B"
    }
  ]
}
```

---

### GET /api/compare/{product_id}

특정 상품의 도매처별 가격 비교. 가격 낮은 순 정렬.

**Path Parameters**

| param      | type | description        |
|------------|------|--------------------|
| product_id | int  | standard_products.id |

**Response**
```json
{
  "product_id": 7,
  "standard_name": "신비복숭아",
  "category": "과일",
  "offer_count": 169,
  "offers": [
    {
      "offer_id": 1234,
      "supplier_name": "공급사A",
      "price": 8000,
      "grade": "상품",
      "weight_value": 2.0,
      "weight_unit": "kg",
      "count": 8,
      "count_unit": "과",
      "cultivation_type": "하우스",
      "package_type": null,
      "match_confidence": 1.0
    }
  ]
}
```

**Errors**
- 404: product_id not found

---

## Review Queue

### GET /api/review

Review Queue 목록. 기본값: status=pending (미매칭 항목).

**Query Parameters**

| param       | type   | default | description                        |
|-------------|--------|---------|------------------------------------|
| status      | string | pending | pending / approved / rejected      |
| supplier_id | int    | null    | 도매처 ID 필터                      |
| limit       | int    | 50      | 최대 반환 수 (1~500)               |
| offset      | int    | 0       | 페이지 오프셋                       |

**Response**
```json
{
  "status": "pending",
  "total": 254,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": 1,
      "original_name": "마하차녹 무지개망고",
      "normalized_attrs": {
        "product_name": "마하차녹 무지개망고",
        "grade": null,
        "weight": null,
        "count": null,
        "cultivation_type": null,
        "tags": []
      },
      "price": 30000,
      "supplier_name": "테스트공급사",
      "file_name": "[2] 공급가 (과일)(1).html",
      "status": "pending",
      "created_at": "2026-06-30 21:39:00"
    }
  ]
}
```

---

### POST /api/review/{id}/approve

Review Queue 항목 승인 → product_aliases에 alias 추가.

**Path Parameters**

| param | type | description        |
|-------|------|--------------------|
| id    | int  | review_queue.id    |

**Request Body**
```json
{
  "standard_product_id": 7,
  "alias": "신비"
}
```

| field               | type   | required | description                             |
|---------------------|--------|----------|-----------------------------------------|
| standard_product_id | int    | yes      | 매핑할 standard_products.id              |
| alias               | string | no       | 추가할 alias (없으면 normalized product_name 사용) |

**Response**
```json
{
  "review_id": 1,
  "alias_added": "신비",
  "standard_product_id": 7,
  "standard_name": "신비복숭아",
  "status": "approved"
}
```

**Errors**
- 404: review_queue id not found
- 400: Already processed (status != pending)
- 404: standard_product_id not found

**Rules**
- standard_products는 절대 자동 수정하지 않음
- alias는 INSERT OR IGNORE (중복 시 무시)
- 승인 즉시 review_queue.status = 'approved'

---

## Import

### POST /api/import

Import Engine 트리거. **로컬 개발 전용.**

**Request Body**
```json
{
  "file_path": "[2] 공급가 (과일)(1).html",
  "supplier_name": "공급사명"
}
```

- `file_path`: 절대경로 또는 `data/raw/` 기준 상대경로

**Response**
```json
{
  "file": "[2] 공급가 (과일)(1).html",
  "supplier_name": "공급사명",
  "total_rows": 127,
  "success_rows": 15,
  "new_products": 112,
  "failed_rows": 0,
  "updated_prices": 3
}
```

**Errors**
- 404: File not found
- 500: Import engine error

**Pipeline**
```
file → Parser → Normalizer → Matcher → DB (Transaction)
                                    ↓
                            matched → product_offers + price_history
                            unmatched → review_queue (dedup: pending 중복 skip)
```

---

## Status Codes

| Code | Meaning                        |
|------|--------------------------------|
| 200  | Success                        |
| 400  | Bad request (already processed)|
| 404  | Resource not found             |
| 500  | Server / import engine error   |

---

## Changelog

| Version | Date       | Changes                                         |
|---------|------------|-------------------------------------------------|
| 0.1.0   | 2026-06-30 | GET /api/health, GET /api/products              |
| 0.3.0   | 2026-06-30 | GET /api/compare, GET /api/review,              |
|         |            | POST /api/review/{id}/approve, POST /api/import |
|         |            | category filter, suppliers list in products,    |
|         |            | review_queue deduplication                      |