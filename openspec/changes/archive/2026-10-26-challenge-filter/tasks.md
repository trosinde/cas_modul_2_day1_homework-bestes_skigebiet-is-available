# Tasks

## 1. Sidebar-Filter

- [x] 1.1 Add "Min. Anspruch" range slider to the sidebar in `components/dashboard/template.html`, between "Grössenklasse" and "Max. Fahrzeit". Range 0–10, step 0.5, default 0. Show current value next to slider (pattern: `<span id="challengeVal">0</span>`). Verify: dashboard loads, slider is visible and draggable.

## 2. Filter-Logik

- [x] 2.1 Read slider value in `getFiltered()` (line ~190) and add filter condition: `if ((r.challenge_score || 0) < minChallenge) return false;`. Verify: setting slider to 5 hides resorts with challenge_score < 5 from table, map, and charts.
- [x] 2.2 Wire `input` event on the new slider to call `render()` (at line ~509, alongside existing `filterDrive` listener). Update the `challengeVal` span in the render function (alongside `driveVal` update at line ~496). Verify: moving the slider live-updates the displayed value and re-renders the dashboard.

## 3. Tooltips

- [x] 3.1 Replace the "Anspruch" column header tooltip (line ~108, inside `<th>Anspruch<span class="th-info">...`) with a user-friendly description: "Höher = anspruchsvolleres Gelände. Bewertet den Anteil roter und schwarzer Pisten, die Vielfalt der Schwierigkeitsgrade und die Gebietsgrösse. Daten aus OpenSkiData." Remove internal formula details (weights, variable names). Verify: hover shows new tooltip text.
- [x] 3.2 Ensure challenge_score cell tooltip shows km breakdown on hover: `title="Blau: X km · Rot: Y km · Schwarz: Z km"` (already present from prior change, verify it works with actual data). Verify: hover over a challenge_score cell in Top 10 shows km values > 0.

## 4. Verifikation

- [x] 4.1 Regenerate dashboard (`python3 -m components.dashboard`), open in browser, verify: slider filters correctly, tooltips display, Pearson correlation still shows "Anspruch", `make test` passes.
