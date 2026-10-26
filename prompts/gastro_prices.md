For each mountain restaurant below, estimate the lunch prices during peak ski season.

CHF to EUR rate: {{chf_to_eur}}

Restaurants to evaluate:
{{batch_list}}

For each restaurant provide:
- lunch_main_eur: price of a standard main course (adult portion), in EUR
- lunch_drink_eur: price of a 0.5l soft drink, in EUR
- price_level: "low" | "medium" | "high" compared to Alpine average
- confidence: "low" | "medium" | "high"
- reason_price: 1–2 sentences explaining the estimate

Return JSON: {"restaurants": [{"restaurant_id": "...", "lunch_main_eur": ..., "lunch_drink_eur": ..., "price_level": "...", "confidence": "...", "reason_price": "..."}]}
