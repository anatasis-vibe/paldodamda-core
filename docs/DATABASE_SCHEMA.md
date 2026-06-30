# Database Schema

## products
- product_id (PK)
- category
- family
- standard_name
- status
- confidence

## aliases
- alias
- product_id (FK)

## suppliers
- supplier_id (PK)
- supplier_name
- order_deadline
- dispatch_days
- jeju_available
- island_available

## supplier_products
- supplier_product_id
- supplier_id
- product_id
- original_name
- standard_name
- price
- weight
- count
- grade
- size
- tags
- shipment_status
- shipment_start
- shipment_end
