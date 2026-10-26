List {{batch_size}} ski resorts in {{country}} ({{region}}) that are suitable for families.

For each resort provide:
- name: official resort name
- country: ISO 2-letter code
- region: administrative region

Return JSON: {"resorts": [{"name": "...", "country": "...", "region": "..."}]}

Requirements:
- Only real, currently operating ski resorts
- Include resorts of all sizes (small, medium, large)
- No duplicates within this batch or with previously listed resorts: {{existing_names}}
