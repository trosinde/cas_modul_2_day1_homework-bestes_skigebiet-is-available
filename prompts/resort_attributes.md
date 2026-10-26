For each ski resort below, provide detailed attributes for a family of 2 adults and children aged 16 and 13 from Singen (Hohentwiel), Germany.

CHF to EUR rate: {{chf_to_eur}}

Resorts to evaluate:
{{batch_list}}

For each resort provide ALL of these attributes:
- lat, lon: coordinates of the main base station (Talstation), decimal degrees
- top_elevation_m: highest lift point in meters
- base_elevation_m: lowest lift point in meters
- slope_km: total piste kilometers as advertised by the resort
- day_pass_adult_eur: adult day pass, peak season, in EUR
- day_pass_youth16_eur: day pass for a 16-year-old, in EUR (use the correct age category!)
- day_pass_child13_eur: day pass for a 13-year-old, in EUR (use the correct age category!)
- age_category_16: name and age range of the category that applies to a 16-year-old (e.g. "Jugend 16-18 Jahre")
- age_category_13: name and age range for a 13-year-old (e.g. "Kind 6-15 Jahre")
- family_pass_eur: family day pass for 2 adults + children 16 and 13, in EUR, or null if not available
- family_pass_conditions: conditions of the family pass (1 sentence), or null
- drive_time_min: driving time from Singen (Hohentwiel) without traffic, in minutes
- drive_distance_km: driving distance from Singen, one way, in km
- snow_reliability: integer 1–10 (1–3 weak, 4–6 average, 7–8 good, 9–10 top 10% of the Alps)
- family_friendliness: integer 1–10, considering kids areas, ski school, easy slopes, family offers
- value_for_money: integer 1–10, value for money for a family of 2 adults and children aged 16 and 13
- confidence: "low" | "medium" | "high" for the factual values
- reason_snow, reason_family, reason_value: 1–2 sentences each explaining the score with concrete facts (e.g. altitude, glacier, snowmaking, specific offers)

Return JSON: {"resorts": [ { "resort_id": "...", ...all attributes... } ]}
