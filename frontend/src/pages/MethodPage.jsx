import React, { useState } from 'react';
import { LEVELS } from '../levels.js';

export function MethodPage() {
  const [activeProfile, setActiveProfile] = useState('acclimatized');

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Screening Methodology & Scientific Basis</h1>
        <p className="page-desc">
          How ShramShield estimates worksite heat strain and transforms meteorological inputs into actionable work/rest schedules.
        </p>
      </div>

      {/* What WBGT is in two sentences */}
      <section className="card method-section" aria-labelledby="what-is-wbgt">
        <h2 id="what-is-wbgt">What is Wet Bulb Globe Temperature (WBGT)?</h2>
        <p>
          Wet Bulb Globe Temperature (WBGT) is an internationally recognized composite index that measures environmental heat stress on the human body by integrating air temperature, humidity, wind speed, and solar radiation. Unlike simple dry-bulb air temperature, WBGT captures the evaporative cooling capacity of sweat and the radiative heat load from direct sun, providing a realistic assessment of occupational heat danger.
        </p>
      </section>

      {/* Five Levels and Max Minutes Per Hour */}
      <section className="card method-section" aria-labelledby="five-levels">
        <h2 id="five-levels">Screening Risk Levels & Hourly Work Allocation</h2>
        <p>
          The screening bands map the applicable WBGT limits to a maximum work allocation and minimum shade-rest period per hour. These estimates support worksite planning but do not guarantee safety.
        </p>

        <div className="backtest-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Risk Level</th>
                <th>Work Allocation</th>
                <th>Max Work (min/hr)</th>
                <th>Min Rest in Shade (min/hr)</th>
                <th>Operational Meaning</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <span className="risk-level-badge" style={{ backgroundColor: LEVELS.GREEN.bg, color: LEVELS.GREEN.text }}>
                    {LEVELS.GREEN.symbol}
                  </span>
                </td>
                <td>Band A (75–100% work)</td>
                <td><strong>60 min</strong></td>
                <td>0 min</td>
                <td>Normal work as planned. Regular hydration prompts.</td>
              </tr>
              <tr>
                <td>
                  <span className="risk-level-badge" style={{ backgroundColor: LEVELS.YELLOW.bg, color: LEVELS.YELLOW.text }}>
                    {LEVELS.YELLOW.symbol}
                  </span>
                </td>
                <td>Band B (50–75% work)</td>
                <td><strong>45 min</strong></td>
                <td>15 min</td>
                <td>Normal monitoring. Enforce scheduled hydration breaks.</td>
              </tr>
              <tr>
                <td>
                  <span className="risk-level-badge" style={{ backgroundColor: LEVELS.ORANGE.bg, color: LEVELS.ORANGE.text }}>
                    {LEVELS.ORANGE.symbol}
                  </span>
                </td>
                <td>Band C (25–50% work)</td>
                <td><strong>30 min</strong></td>
                <td>30 min</td>
                <td>Elevated heat stress. Increase shade rest periods.</td>
              </tr>
              <tr>
                <td>
                  <span className="risk-level-badge" style={{ backgroundColor: LEVELS.RED.bg, color: LEVELS.RED.text }}>
                    {LEVELS.RED.symbol}
                  </span>
                </td>
                <td>Band D (0–25% work)</td>
                <td><strong>15 min</strong></td>
                <td>45 min</td>
                <td>High heat strain. Active supervisor monitoring, cool water.</td>
              </tr>
              <tr>
                <td>
                  <span className="risk-level-badge" style={{ backgroundColor: LEVELS.STOP.bg, color: LEVELS.STOP.text }}>
                    {LEVELS.STOP.symbol}
                  </span>
                </td>
                <td>Above Every Screening Limit</td>
                <td><strong>0 min</strong></td>
                <td>60 min</td>
                <td>Halt non-essential work. Only emergency tasks with supervisor.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Published Screening Limits Table */}
      <section className="card method-section" aria-labelledby="screening-limits-table">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.85rem' }}>
          <h2 id="screening-limits-table" style={{ margin: 0 }}>
            ACGIH Screening Limits Table (WBGT Thresholds in °C)
          </h2>
          <div className="nav-links" style={{ display: 'inline-flex' }}>
            <button
              type="button"
              className={`nav-link ${activeProfile === 'acclimatized' ? 'active' : ''}`}
              onClick={() => setActiveProfile('acclimatized')}
              style={{ border: 'none', cursor: 'pointer' }}
            >
              Acclimatized Workers
            </button>
            <button
              type="button"
              className={`nav-link ${activeProfile === 'unacclimatized' ? 'active' : ''}`}
              onClick={() => setActiveProfile('unacclimatized')}
              style={{ border: 'none', cursor: 'pointer' }}
            >
              Unacclimatized Workers
            </button>
          </div>
        </div>

        <p>
          Derived from the published <em>ACGIH 2026 TLV Table 1</em> (as summarized by CCOHS). Screening limits are defined for an 8-hour workday across four metabolic workload categories:
        </p>

        <div className="backtest-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Workload Category</th>
                <th className="num">Band A (&le; 60m work)</th>
                <th className="num">Band B (&le; 45m work)</th>
                <th className="num">Band C (&le; 30m work)</th>
                <th className="num">Band D (&le; 15m work)</th>
              </tr>
            </thead>
            <tbody>
              {activeProfile === 'acclimatized' ? (
                <>
                  <tr>
                    <td><strong>Light</strong></td>
                    <td className="num">31.0°C</td>
                    <td className="num">31.0°C</td>
                    <td className="num">32.0°C</td>
                    <td className="num">32.5°C</td>
                  </tr>
                  <tr>
                    <td><strong>Moderate</strong></td>
                    <td className="num">28.0°C</td>
                    <td className="num">29.0°C</td>
                    <td className="num">30.0°C</td>
                    <td className="num">31.5°C</td>
                  </tr>
                  <tr>
                    <td><strong>Heavy</strong></td>
                    <td className="num">— (No allowance)</td>
                    <td className="num">27.5°C</td>
                    <td className="num">29.0°C</td>
                    <td className="num">30.5°C</td>
                  </tr>
                  <tr>
                    <td><strong>Very Heavy</strong></td>
                    <td className="num">— (No allowance)</td>
                    <td className="num">— (No allowance)</td>
                    <td className="num">28.0°C</td>
                    <td className="num">30.0°C</td>
                  </tr>
                </>
              ) : (
                <>
                  <tr>
                    <td><strong>Light</strong></td>
                    <td className="num">28.0°C</td>
                    <td className="num">28.5°C</td>
                    <td className="num">29.5°C</td>
                    <td className="num">30.0°C</td>
                  </tr>
                  <tr>
                    <td><strong>Moderate</strong></td>
                    <td className="num">25.0°C</td>
                    <td className="num">26.0°C</td>
                    <td className="num">27.0°C</td>
                    <td className="num">29.0°C</td>
                  </tr>
                  <tr>
                    <td><strong>Heavy</strong></td>
                    <td className="num">— (No allowance)</td>
                    <td className="num">24.0°C</td>
                    <td className="num">25.5°C</td>
                    <td className="num">28.0°C</td>
                  </tr>
                  <tr>
                    <td><strong>Very Heavy</strong></td>
                    <td className="num">— (No allowance)</td>
                    <td className="num">— (No allowance)</td>
                    <td className="num">24.5°C</td>
                    <td className="num">27.0°C</td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)', marginTop: '0.5rem' }}>
          Note: Cells with "—" indicate that published screening standards do not support full-shift continuous work at that metabolic workload. The best reachable level is capped, and the UI transparently displays this limit.
        </p>
      </section>

      {/* Authoritative Data Sources */}
      <section className="card method-section" aria-labelledby="data-sources">
        <h2 id="data-sources">Primary Data & Algorithmic Sources</h2>
        <ul className="caveats-list">
          <li>
            <strong>Open-Meteo Weather API:</strong> Provides hourly forecasts and reanalysis data (air temperature at 2m, relative humidity, surface pressure, 10m wind speed, shortwave solar radiation, and direct radiation) without proprietary vendor lock-in.
          </li>
          <li>
            <strong>ECMWF thermofeel (Liljegren Algorithm):</strong> Industrial-grade atmospheric physics implementation (Apache 2.0 licence) computing outdoor Wet Bulb Globe Temperature using solar zenith calculations and heat-balance equations.
          </li>
          <li>
            <strong>ACGIH / CCOHS Screening Limits:</strong> Threshold Limit Values (TLV) for chemical and physical substances, published by the American Conference of Governmental Industrial Hygienists and summarized by the Canadian Centre for Occupational Health and Safety.
          </li>
          <li>
            <strong>OHCOW Heat Response Guidance:</strong> Hydration protocol recommending approximately 240 mL (1 cup) of cool water every 20 minutes during thermal stress.
          </li>
        </ul>
      </section>

      {/* Honest "What this is not" paragraph */}
      <section className="card method-section" style={{ borderLeft: '5px solid #64748b', background: '#f8fafc' }} aria-labelledby="what-this-is-not">
        <h2 id="what-this-is-not">What This System Is Not (Limitations & Honesty)</h2>
        <p>
          ShramShield is an operational screening tool driven by weather-model estimations; it is <strong>not an on-site physical sensor measurement</strong>, nor is it a clinical medical diagnosis. The recommendations generated are derived from city-scale meteorological models and do not account for hyper-local microclimates (such as reflected heat from bitumen, hot sheet-metal roofs, or confined boiler rooms).
        </p>
        <p>
          Furthermore, these screening limits assume a standardized 8-hour workday for young, healthy adults and have not been validated against individual medical histories, age, clothing insulation, or illness reports. They are not a medical prescription. Site supervisors and workers must always exercise on-site judgment, observe individual symptoms, and stop work immediately if anyone feels dizzy, nauseous, fatigued, or unwell.
        </p>
      </section>

      <section className="card method-section" aria-labelledby="limitations-list-heading">
        <h2 id="limitations-list-heading">Limitations</h2>
        <ul className="caveats-list">
          <li>Compares two methods on the same historical data; it is not validated against heat illness cases.</li>
          <li>Uses historical reanalysis data, not archived forecasts, so real-time forecast error is not included.</li>
          <li>WBGT is estimated from modelled weather at a city point, not measured at the worksite.</li>
          <li>Screening limits are for an 8-hour workday and are not a prescription of work and rest periods.</li>
          <li>Live plans rest on a forecast, which carries its own error; a plan can be wrong about the day ahead even when the method is right.</li>
          <li>Reanalysis weather is a grid value of roughly 10 to 25 km, so it can differ from a nearby station, and a city point is not the site.</li>
          <li>Microclimate is not modelled at all. Bitumen, metal roofs, trenches, reflective walls and heavy or impermeable clothing can all make real exposure considerably worse than these numbers.</li>
          <li>People differ. Age, fitness, medication, illness, pregnancy, hydration and acclimatization state all change individual risk, and the screening limits are not a medical standard that fits everyone.</li>
          <li>The Hindi message text is machine-drafted and has not been reviewed by a native Hindi speaker.</li>
          <li>In 6 of the 8736 hours examined, all with wind below the 0.62 m/s floor that the Liljegren method applies, WBGT exceeded air temperature by more than 3 C. This is expected for a sunlit globe in near-still air rather than an error, and those hours are reported explicitly by core/scripts/run_backtest.py instead of being hidden.</li>
        </ul>
        <p className="hindi-review-status">Hindi text review: pending native review</p>
      </section>
    </div>
  );
}
