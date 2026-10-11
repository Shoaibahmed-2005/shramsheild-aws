import React, { useState, useEffect } from 'react';
import { getBacktest } from '../api.js';
import { buildBacktestHeadline } from '../utils.js';
import { LEVELS, getLevelConfig } from '../levels.js';

export function BacktestPage() {
  const [backtest, setBacktest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchBacktestData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getBacktest();
      setBacktest(res);
    } catch (err) {
      setError(err.message || 'Failed to load historical backtest');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBacktestData();
  }, []);

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Historical Heatwave Backtest</h1>
          <p className="page-desc">Replaying April - June 2024 hourly weather data across India.</p>
        </div>
        <div className="card skeleton skeleton-card" style={{ height: '300px' }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-card" role="alert">
        <h1 className="error-title" style={{ fontSize: '1.2rem' }}>Unable to Load Backtest Data</h1>
        <p className="error-msg">{error}</p>
        <button type="button" className="btn-retry" onClick={fetchBacktestData}>
          Retry Loading
        </button>
      </div>
    );
  }

  if (!backtest) return null;

  const isFixture = Boolean(backtest._fixture);
  const headline = buildBacktestHeadline(backtest);
  const maxDangerousSite = Math.max(...(backtest.sites || []).map((s) => s.dangerous_hours || 0), 1);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Historical Heatwave Backtest (April – June 2024)</h1>
        <p className="page-desc">
          Comparing WBGT screening limits (RED and STOP) against traditional air-temperature threshold alerts.
        </p>
      </div>

      {isFixture && (
        <div className="fixture-banner" role="status" aria-label="Demo fixture data badge">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm.75 4.75a.75.75 0 00-1.5 0v4.5a.75.75 0 001.5 0v-4.5zm-.75 8a.9.9 0 110-1.8.9.9 0 010 1.8z" />
          </svg>
          <span><strong>DEMO DATA (fixture)</strong> — Synthesized backtest data</span>
        </div>
      )}

      {/* Headline Sentence Box */}
      <section className="headline-card" aria-label="Backtest findings headline">
        <p className="headline-text">{headline}</p>
      </section>

      {/* Threshold Comparison Table */}
      <section className="card" style={{ marginBottom: '1.5rem' }} aria-labelledby="threshold-table-heading">
        <h2 id="threshold-table-heading" className="card-title">
          Threshold Comparison: Plain Temperature Alerts vs. WBGT Limits
        </h2>
        <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
          Total dangerous work hours across all 4 cities (RED or STOP): <strong>{backtest.totals?.dangerous_hours}</strong>
        </p>

        <div className="backtest-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Air Temp Alert Threshold</th>
                <th className="num">Air Temp Alert Hours</th>
                <th className="num">Caught by Alert</th>
                <th className="num">Dangerous Hours Missed</th>
                <th className="num highlight-col">Missed %</th>
                <th className="num">False Alarms (Low Risk)</th>
              </tr>
            </thead>
            <tbody>
              {backtest.totals?.by_threshold?.map((row) => (
                <tr key={row.threshold_c}>
                  <td><strong>&ge; {row.threshold_c}°C</strong></td>
                  <td className="num">{row.alert_hours} hrs</td>
                  <td className="num">{row.caught} hrs</td>
                  <td className="num">{row.missed} hrs</td>
                  <td className="num highlight-col">
                    {typeof row.missed_pct === 'number' ? row.missed_pct.toFixed(1) : row.missed_pct}%
                  </td>
                  <td className="num">{row.false_alarm_hours} hrs</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* City Breakdown Bars & Example Hour */}
      <div className="plan-two-col">
        {/* City-by-city Breakdown */}
        <section className="card" aria-labelledby="city-breakdown-heading">
          <h2 id="city-breakdown-heading" className="card-title">
            Dangerous Hours by Monitored City
          </h2>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-tertiary)', marginBottom: '0.75rem' }}>
            Work hours reaching RED or STOP screening limits (out of 1,001 work hours):
          </p>
          <div className="city-bars-list">
            {backtest.sites?.map((site) => {
              const pct = ((site.dangerous_hours / maxDangerousSite) * 100).toFixed(0);
              const totalPct = (((site.dangerous_hours || 0) / (site.work_hours_total || 1001)) * 100).toFixed(1);
              return (
                <div key={site.site_id} className="city-bar-item">
                  <div className="city-bar-header">
                    <span>{site.name}</span>
                    <span>
                      {site.dangerous_hours} hrs ({totalPct}% of shift)
                    </span>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${pct}%` }}
                      role="progressbar"
                      aria-valuenow={site.dangerous_hours}
                      aria-valuemin="0"
                      aria-valuemax={maxDangerousSite}
                      aria-label={`${site.name}: ${site.dangerous_hours} dangerous hours`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Example Hour Callout */}
        <section className="card" aria-labelledby="example-hour-heading">
          <h2 id="example-hour-heading" className="card-title">
            Case Study: The "Invisible" Danger Hour
          </h2>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '0.85rem' }}>
            A plain 40°C temperature alert misses dangerous humid hours completely:
          </p>
          {backtest.sites?.[0]?.example_hour && (
            <div style={{ background: 'var(--bg-card-alt)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <strong style={{ fontSize: '0.95rem' }}>{backtest.sites[0].name}</strong>
                <span className="risk-level-badge" style={{ backgroundColor: LEVELS.RED.bg, color: LEVELS.RED.text, fontSize: '0.72rem' }}>
                  {backtest.sites[0].example_hour.level}
                </span>
              </div>
              <p style={{ fontSize: '0.86rem', color: 'var(--text-tertiary)', marginBottom: '0.5rem' }}>
                Timestamp: {backtest.sites[0].example_hour.time.replace('T', ' at ')} IST
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.88rem' }}>
                <div>Air Temp: <strong>{backtest.sites[0].example_hour.air_temp_c}°C</strong> (Below 40°C alert!)</div>
                <div>Relative Humidity: <strong>{backtest.sites[0].example_hour.rh_pct}%</strong></div>
                <div>Calculated WBGT: <strong>{backtest.sites[0].example_hour.wbgt_c}°C</strong></div>
                <div>Screening Limit: <strong>RED (15 min work/hr)</strong></div>
              </div>
              <p style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Result: With 84% humidity, workers face severe heat strain at 28.8°C air temperature, but simple thermometers trigger zero alerts.
              </p>
            </div>
          )}
        </section>
      </div>

      {/* Caveats & Methodological Disclaimers */}
      <section className="card" aria-labelledby="caveats-heading">
        <h2 id="caveats-heading" className="card-title">
          Methodological Caveats & Integrity Notes
        </h2>
        <ul className="caveats-list">
          {backtest.caveats?.map((caveat, idx) => (
            <li key={idx}>{caveat}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
