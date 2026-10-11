# ShramShield — Frontend Design Summary

**Document owner:** P3 (Frontend and Story)  
**Reference documents:** `AGENTS.md`, `docs/BUILD_PLAN.md` (Sections 0, 3, and P3.1), `docs/design/NOTES.md`, and reference images (`dashboard.png`, `sites_monitoring.png`, `sites_monitoring2.png`, `heatmap.png`, `backtest.png`).

---

## 1. Visual Direction & Mood

The visual direction for ShramShield is a modern, high-contrast, clean operations dashboard inspired by soft-surfaced, pastel-accented interfaces. It communicates operational rigor, occupational safety, and clarity under high-stress conditions.

- **Mood:** Clean, minimal, reliable, operational, and accessible.
- **Tone:** Objective and scientific—never playful, cartoonish, or cluttered.
- **Design Metaphor:** An industrial safety operations console tailored for worksite managers, supervisors, and safety officers in India.

---

## 2. Layout Structure & Navigation

- **Navigation Pattern:**
  - Compact top header with brand identity: ShramShield shield motif, title "ShramShield", and subtitle "HEAT SAFETY OPERATIONS".
  - Nav pills / tabs linking to the contract-specified hash routes:
    - `#/` — Sites Dashboard
    - `#/site/{site_id}` — Site Plan
    - `#/backtest` — Historical Reanalysis Backtest
    - `#/method` — Scientific Methodology & Screening Limits
  - Top action controls: Language toggle (**EN / HI**) for safety messages and advice.
  - Page header with single `<h1>` per route for semantic accessibility.
  - Generous padding and maximum width constraint (`1280px`) centered on larger viewports.
  - Fully responsive down to `360px` mobile viewports with flexible grid and auto-wrapping columns.
  - Persistent footer on every page containing the mandatory project disclaimer.

---

## 3. Colour Palette

### 3.1 Interface Base Palette (Pastel & Clean)
- **App Background:** `#f3f6f9` (soft warm off-white / very light slate).
- **Card Background:** `#ffffff` (pure white) with subtle border `#e2e8f0` and soft shadow `0 2px 8px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.06)`.
- **Card Muted Surface:** `#f8fafc` for nested detail panels and metric blocks.
- **Primary Text:** `#0f172a` (slate-900) for sharp legibility.
- **Secondary Text:** `#475569` (slate-600) for labels, metadata, and timestamps.
- **Tertiary Text / Border:** `#94a3b8` / `#cbd5e1`.
- **Primary Accent:** `#2563eb` (royal blue) for active tabs and interactive controls.

### 3.2 Heat-Risk Classification Colours (Mandatory Contract Priority)
The contract-defined risk levels take absolute priority over pastel tones for safety compliance. All combinations meet WCAG AA contrast (≥ 4.5:1):
- **GREEN (LOW):** Background `#1b7f3b`, Text `#ffffff` (Contrast ~ 5.3:1)
- **YELLOW (MODERATE):** Background `#f2c200`, Text `#111111` (Contrast ~ 10.7:1)
- **ORANGE (HIGH):** Background `#e8710a`, Text `#111111` (Contrast ~ 5.2:1)
- **RED (VERY HIGH):** Background `#c62828`, Text `#ffffff` (Contrast ~ 5.7:1)
- **STOP (EXTREME):** Background `#5b0f12`, Text `#ffffff` (Contrast ~ 12.8:1)
- **UNKNOWN (NO DATA):** Background `#6b7280`, Text `#ffffff` (Contrast ~ 4.7:1)

*Rule:* Heat-risk levels are always paired with distinct text labels (e.g. "LOW", "MODERATE", "HIGH", "VERY HIGH", "EXTREME", "NO DATA"). Colour is never the sole indicator.

---

## 4. Typography

- **Font Family:** `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Devanagari", "Nirmala UI", sans-serif`.
  - Built-in Devanagari fallbacks (`"Noto Sans Devanagari"`, `"Nirmala UI"`) ensure crisp Hindi rendering without requiring external web font downloads.
- **Type Scale:**
  - `h1`: `1.75rem` (`28px`), font-weight 700.
  - `h2`: `1.25rem` (`20px`), font-weight 600.
  - `h3` / section title: `1.05rem` (`17px`), font-weight 600.
  - Body text: `0.95rem` (`15px`), font-weight 400 / 500.
  - Small labels & captions: `0.78rem` (`12.5px`), font-weight 500 / 600, uppercase letter-spacing `0.04em`.
- **Zoom & Accessibility:** Fully fluid and scalable up to 200% browser zoom without layout breakage.

---

## 5. Card Styling & Spacing

- **Corner Radius:**
  - Main cards: `16px`.
  - Metric chips & sub-cards: `10px` – `12px`.
  - Buttons & navigation pills: `8px` – `10px`.
  - Heat strip cells: `8px`.
- **Spacing Scale:** Multiples of 4px (`8px`, `12px`, `16px`, `20px`, `24px`, `32px`).
- **Focus Indicators:** Explicit, high-visibility focus outline (`3px solid #2563eb`, offset `2px`) on all interactive buttons, strip cells, and links for full keyboard navigability.

---

## 6. Component-Specific Design Guidance

### 6.1 Sites Dashboard (`#/`)
- Grid of site cards displaying site name, location, workload profile, shift hours, preferred language, and immediate link to view the daily plan.
- Empty, loading (skeleton pulse), and error states with retry buttons.

### 6.2 Site Plan (`#/site/{site_id}`)
- **Header:** Site title, site ID, geographic coordinates, and profile summary pill (`workload`, `acclimatized`, `work_start_hour` to `work_end_hour`).
- **Fixture Badge:** High-visibility banner `DEMO DATA (fixture)` whenever loaded data contains `_fixture: true`.
- **24-Hour Heat Strip:**
  - 24 cells representing all hours of the day (00:00 to 23:00).
  - Work hours feature full level color badges.
  - Non-work hours are visibly dimmed with clear "Off shift" indication.
  - Each cell is a native, focusable `<button>` with full `aria-label` describing time, risk level, WBGT, and work limit.
  - Selected cell displays a highlight ring.
- **Selected Hour Inspection Panel:**
  - Shows environmental parameters: Air Temp (°C), Relative Humidity (%), Wind Speed (m/s), Solar Radiation (W/m²).
  - Derived index: WBGT (°C).
  - Operational guidance: Max work minutes/hr, Min rest minutes/hr in shade.
  - Explicit explanation: exact `reason` text from the plan.
- **Today's Risk Windows:** Runs of consecutive work hours with non-GREEN risk levels.
- **Supervisor Message Card:**
  - Displays generated notification in selected language (English or Hindi).
  - Copy-to-clipboard action with visual feedback.

### 6.3 Backtest Page (`#/backtest`)
- **Headline Summary:** Plain-language synthesis of missed dangerous hours during April–June 2024 heatwaves.
- **Threshold Comparison Table:** Comparing baseline temperature thresholds (37°C, 40°C, 42°C) against WBGT screening limits (Dangerous hours, Caught, Missed, Missed %, False alarms).
- **City Breakdown Bars:** Native CSS horizontal bars representing dangerous hours per city with numerical values.
- **Example Hour Callout:** The exact hour demonstrating high humidity + solar radiation causing dangerous WBGT despite moderate air temperature.
- **Caveats & Methodological Disclaimers:** Explicitly displayed.

### 6.4 Method Page (`#/method`)
- Clear 2-sentence explanation of WBGT.
- Visual breakdown of the 5 ACGIH-based risk levels and work/rest screening limits.
- Authoritative reference sources: Open-Meteo, ECMWF thermofeel, ACGIH / CCOHS.
- Transparent "What this is not" section emphasising screening nature vs. medical certification.

---

## 7. What Should & Should NOT Be Taken from References

### What TO Take:
1. **Clean Card-Based Architecture:** Soft cards with subtle shadows, rounded borders, and distinct content hierarchies.
2. **Horizontal Strip Presentation:** The 24-hour visual strip for hourly heat progression.
3. **Structured Metric Blocks:** Clear, modular display of weather inputs alongside derived WBGT and work/rest recommendations.
4. **Subtle Operational Aesthetic:** Professional color scheme and readable typography.

### What NOT to Take:
1. **NO Emojis:** Strictly prohibited by design rules. Use semantic labels and clean SVG/CSS indicators.
2. **NO Human Faces, Avatars, or Worker Illustrations:** No stock photos, cartoon workers, avatars, or decorative people illustrations.
3. **NO External UI / Chart Frameworks:** Pure CSS, HTML, and React. No external charting libraries (e.g. Chart.js, Recharts) or CSS frameworks (e.g. Tailwind, Bootstrap).
4. **NO Invented Features or Data:** Do not include unrelated cards from mockups such as calorie counters, sunrise/sunset times, mock maps, or fake weather forecasts.
5. **NO Modification of Risk Colours:** The reference images must never override the contract-specified risk level colors.
