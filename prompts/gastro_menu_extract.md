Extract all main courses (Hauptgerichte) with prices from this restaurant menu.

Rules:
- Only main courses: no starters, soups, salads, desserts, drinks, or sides
- Each item: name and price in EUR
- If prices are in CHF, convert at rate {{chf_to_eur}}
- If a dish has multiple sizes/variants, use the standard/regular portion
- Also extract the price of a 0.5L soft drink (Cola, Fanta, Sprite or similar) if listed

Menu content:
{{menu_text}}

Return JSON:
{
  "items": [
    {"name": "Käsespätzle", "price_eur": 16.50},
    {"name": "Wiener Schnitzel", "price_eur": 22.00}
  ],
  "drink_05l_eur": 4.50,
  "currency_detected": "CHF",
  "menu_language": "de"
}

If no main courses can be identified, return: {"items": [], "drink_05l_eur": null, "currency_detected": null, "menu_language": null}
