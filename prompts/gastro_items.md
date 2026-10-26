List {{batch_size}} mountain restaurants in the ski areas of {{region}}, {{country}} that serve skiers during winter season.

For each restaurant provide:
- name: restaurant name
- country: "{{country_code}}"
- region: "{{region}}"
- lat: latitude (decimal degrees)
- lon: longitude (decimal degrees)
- elevation_m: altitude in meters
- restaurant_type: "self_service" | "hut" | "restaurant"
- ski_area_hint: name of the ski resort this restaurant belongs to (your best guess), or null

Return JSON: {"restaurants": [{"name": "...", ...}]}

Requirements:
- Only real, currently operating mountain restaurants
- Include a mix of self-service, huts, and restaurants
- No duplicates within this batch or with previously listed: {{existing_names}}
