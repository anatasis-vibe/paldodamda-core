# Claude Rules — PaldoDamdA OS

- Never edit Product Master (standard_products) automatically.
- Add new Alias (product_aliases) only after human review.
- Rule Book (attribute_rules) executes before Alias search.
- One standard product per product_name only.
- Preserve Family structure in product hierarchy.
- Unknown products go to Review Queue — never discard.
- Every import must be reversible (transaction + import_history).
- Never mutate Product Master automatically.
- failed_rows = actual row errors (exceptions), NOT review_queue entries.
- new_products = unmatched rows in review_queue.