import React, { useState, useEffect } from 'react';
import { getSite, getPlan } from '../api.js';
import { LEVELS, getLevelConfig } from '../levels.js';
import { formatHourEn, formatHourHi, formatHour } from '../utils.js';

function indiaDateOffset(offset) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  const date = new Date(Date.UTC(values.year, Number(values.month) - 1, Number(values.day) + offset));
  return date.toISOString().slice(0, 10);
}

function generatedTimeIndia(timestamp) {
  if (!timestamp) return null;
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit'
  }).format(new Date(timestamp));
}

export function SitePlanPage({ siteId, language = 'en' }) {
  const [site, setSite] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedHourIndex, setSelectedHourIndex] = useState(null);
  const [copied, setCopied] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => indiaDateOffset(0));
  const [cacheStatus, setCacheStatus] = useState(null);

  const dateOptions = [
    { label: 'Yesterday', value: indiaDateOffset(-1) },
    { label: 'Today', value: indiaDateOffset(0) },
    { label: 'Tomorrow', value: indiaDateOffset(1) },
    { label: 'Day after', value: indiaDateOffset(2) },
  ];

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [siteRes, planRes] = await Promise.all([
        getSite(siteId),
        getPlan(siteId, selectedDate)
      ]);
      setSite(siteRes);
      setPlan(planRes.plan);
      setCacheStatus(planRes.cache);

      // Default selected hour: peak hour or first work hour with danger, else peak_hour
      if (planRes.plan?.summary?.peak_hour !== undefined && planRes.plan.summary.peak_hour !== null) {
        setSelectedHourIndex(planRes.plan.summary.peak_hour);
      } else if (planRes.plan?.hours?.length > 0) {
        const firstWork = planRes.plan.hours.find((h) => h.in_work_hours);
        setSelectedHourIndex(firstWork ? firstWork.hour : 12);
      }
    } catch (err) {
      setError(err.message || `Failed to load plan for site ${siteId}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [siteId, selectedDate]);

  const handleCopyMessage = (text) => {
    if (!text) return;
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Loading Heat Plan...</h1>
          <p className="page-desc">Fetching site parameters and hourly WBGT screening model.</p>
        </div>
        <div className="card skeleton skeleton-card" style={{ height: '300px' }} />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div style={{ marginBottom: '1rem' }}>
          <a href="#/" style={{ color: 'var(--primary)', textDecoration: 'none', fontWeight: 600 }}>
            &larr; Back to all worksites
          </a>
        </div>
        <div className="error-card" role="alert">
          <h1 className="error-title" style={{ fontSize: '1.25rem' }}>Daily Plan Not Available</h1>
          <p className="error-msg">{error}</p>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button type="button" className="btn-retry" onClick={fetchData}>
              Retry Loading
            </button>
            <a href="#/" className="btn-retry" style={{ background: '#475569', textDecoration: 'none' }}>
              Select Another Site
            </a>
          </div>
        </div>
      </div>
    );
  }

  if (!plan) return null;

  const isFixture = Boolean(plan._fixture);
  const selectedHour = plan.hours?.find((h) => h.hour === selectedHourIndex) || plan.hours?.[12];
  const selectedLevelConfig = getLevelConfig(selectedHour?.level);

  // Profile text: e.g. "Moderate work, acclimatized, 7 AM to 6 PM"
  const startHourStr = formatHourEn(site?.work_start_hour ?? 7);
  const endHourStr = formatHourEn(site?.work_end_hour ?? 18);
  const workloadStr = (site?.workload || plan.profile?.workload || 'moderate');
  const acclimatizedStr = (site?.acclimatized ?? plan.profile?.acclimatized ?? true) ? 'acclimatized' : 'unacclimatized';
  const profileLine = `${workloadStr.charAt(0).toUpperCase() + workloadStr.slice(1)} work, ${acclimatizedStr}, ${startHourStr} to ${endHourStr}`;

  // Message in selected language
  const activeMessage = plan.messages?.[language] || plan.messages?.en || '';

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <a href="#/" style={{ color: 'var(--primary)', textDecoration: 'none', fontWeight: 600, fontSize: '0.9rem' }}>
          &larr; Back to all worksites
        </a>
      </div>

      {isFixture && (
        <div className="fixture-banner" role="status" aria-label="Demo fixture data badge">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm.75 4.75a.75.75 0 00-1.5 0v4.5a.75.75 0 001.5 0v-4.5zm-.75 8a.9.9 0 110-1.8.9.9 0 010 1.8z" />
          </svg>
          <span><strong>DEMO DATA (fixture)</strong> — Precomputed screening fixture for demonstration</span>
        </div>
      )}

      <div className="plan-hero">
        <h1 className="page-title">{site?.name || plan.site_id}</h1>
        <div className="plan-site-meta">
          <span className="site-id-badge" style={{ fontSize: '0.85rem' }}>ID: {site?.site_id || plan.site_id}</span>
          <span className="profile-pill">{profileLine}</span>
          <span className="profile-pill">Date: {plan.date}</span>
          <span className="profile-pill">
            Peak: {plan.summary?.peak_wbgt_c?.toFixed(1)}°C at {formatHourEn(plan.summary?.peak_hour)}
          </span>
        </div>
        <div className="plan-freshness" role="status">
          {cacheStatus === 'HIT' && 'Data loaded from cache.'}
          {cacheStatus === 'MISS' && 'Fresh plan data.'}
          {generatedTimeIndia(plan.generated_at) && ` Generated ${generatedTimeIndia(plan.generated_at)} India time.`}
        </div>
      </div>

      <section className="date-selector" aria-label="Plan date">
        <span>Plan date</span>
        <div role="group" aria-label="Choose plan date">
          {dateOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={selectedDate === option.value ? 'date-option active' : 'date-option'}
              aria-pressed={selectedDate === option.value}
              onClick={() => setSelectedDate(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      {/* 24-Hour Heat Strip */}
      <section className="heat-strip-wrapper" aria-labelledby="heat-strip-heading">
        <div className="heat-strip-header">
          <h2 id="heat-strip-heading" style={{ fontSize: '1.15rem', fontWeight: 700 }}>
            24-Hour Heat Strip (WBGT Screening)
          </h2>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)' }}>
            Click or keyboard Tab to inspect hour details
          </span>
        </div>

        <div className="heat-strip-grid" role="group" aria-label="Hourly WBGT schedule">
          {plan.hours?.map((h) => {
            const lvl = getLevelConfig(h.level);
            const isSelected = h.hour === selectedHourIndex;
            const hourLabel = formatHourEn(h.hour);
            const ariaDesc = h.in_work_hours
              ? `${hourLabel}: ${lvl.symbol}, WBGT ${h.wbgt_c !== null ? h.wbgt_c.toFixed(1) : 'N/A'} C, work ${h.max_work_min ?? 0} minutes per hour`
              : `${hourLabel}: Off shift, WBGT ${h.wbgt_c !== null ? h.wbgt_c.toFixed(1) : 'N/A'} C`;

            const bgCol = h.in_work_hours ? lvl.bg : '#64748b';
            const textCol = h.in_work_hours ? lvl.text : '#ffffff';

            return (
              <button
                key={h.hour}
                type="button"
                className={`heat-cell-btn ${!h.in_work_hours ? 'off-work' : ''} ${isSelected ? 'selected' : ''}`}
                style={{ backgroundColor: bgCol, color: textCol }}
                onClick={() => setSelectedHourIndex(h.hour)}
                aria-pressed={isSelected}
                aria-label={ariaDesc}
              >
                <span className="heat-cell-hour">{hourLabel}</span>
                <span className="heat-cell-level">
                  {h.in_work_hours ? lvl.symbol : 'OFF'}
                </span>
                {h.wbgt_c !== null && (
                  <span style={{ fontSize: '0.62rem', opacity: 0.9 }}>
                    {h.wbgt_c.toFixed(0)}°
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Legend */}
        <div className="legend-bar" aria-label="Risk level legend">
          {Object.values(LEVELS).map((lvl) => (
            <div key={lvl.key} className="legend-item">
              <span className="legend-dot" style={{ backgroundColor: lvl.bg }} />
              <span>{lvl.symbol}</span>
            </div>
          ))}
          <div className="legend-item" style={{ marginLeft: 'auto', opacity: 0.7 }}>
            <span style={{ fontStyle: 'italic' }}>Dimmed cells = Off shift hours</span>
          </div>
        </div>
      </section>

      {/* Detail Panel for Selected Hour */}
      {selectedHour && (
        <section className="hour-detail-panel" aria-labelledby="selected-hour-heading">
          <div className="detail-header">
            <div className="detail-time-title">
              <h3 id="selected-hour-heading">
                Selected Hour: {formatHourEn(selectedHour.hour)} ({selectedHour.time ? selectedHour.time.split('T')[1] : ''} IST)
              </h3>
              {!selectedHour.in_work_hours && (
                <span className="profile-pill" style={{ background: '#f1f5f9' }}>
                  Off-Shift Hour
                </span>
              )}
            </div>
            <div
              className="risk-level-badge"
              style={{
                backgroundColor: selectedLevelConfig.bg,
                color: selectedLevelConfig.text
              }}
            >
              <span>{selectedLevelConfig.symbol}</span>
              <span>— {selectedLevelConfig.name[language] || selectedLevelConfig.name.en}</span>
            </div>
          </div>

          <div className="metrics-grid">
            <div className="metric-card highlight wbgt-card">
              <span className="metric-title">WBGT Index</span>
              <span className="metric-val" style={{ color: selectedLevelConfig.bg }}>
                {selectedHour.wbgt_c !== null ? selectedHour.wbgt_c.toFixed(1) : 'N/A'}
                <span className="metric-unit">°C</span>
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-title">Air Temp</span>
              <span className="metric-val">
                {selectedHour.air_temp_c !== null ? selectedHour.air_temp_c.toFixed(1) : 'N/A'}
                <span className="metric-unit">°C</span>
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-title">Relative Humidity</span>
              <span className="metric-val">
                {selectedHour.rh_pct ?? 'N/A'}
                <span className="metric-unit">%</span>
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-title">Wind Speed</span>
              <span className="metric-val">
                {selectedHour.wind_ms !== null ? selectedHour.wind_ms.toFixed(1) : 'N/A'}
                <span className="metric-unit">m/s</span>
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-title">Solar Radiation</span>
              <span className="metric-val">
                {selectedHour.ghi_wm2 ?? 0}
                <span className="metric-unit">W/m²</span>
              </span>
            </div>
            <div className="metric-card highlight">
              <span className="metric-title">Max Work Allocation</span>
              <span className="metric-val">
                {selectedHour.in_work_hours
                  ? `${selectedHour.max_work_min ?? 0}`
                  : '—'}
                <span className="metric-unit">{selectedHour.in_work_hours ? 'min/hr' : ''}</span>
              </span>
            </div>
            <div className="metric-card highlight">
              <span className="metric-title">Min Rest (In Shade)</span>
              <span className="metric-val">
                {selectedHour.in_work_hours
                  ? `${selectedHour.min_rest_min ?? 0}`
                  : '—'}
                <span className="metric-unit">{selectedHour.in_work_hours ? 'min/hr' : ''}</span>
              </span>
            </div>
          </div>

          {selectedHour.reason && (
            <div className="reason-box">
              <strong>Screening Limit Evaluation:</strong>
              {selectedHour.reason}
            </div>
          )}
        </section>
      )}

      {/* Windows and Message Cards */}
      <div className="plan-two-col">
        {/* Today's Windows */}
        <section className="card" aria-labelledby="windows-heading">
          <h2 id="windows-heading" className="card-title">
            Today's Risk Windows
          </h2>
          {plan.summary?.windows?.length > 0 ? (
            <div>
              {plan.summary.windows.map((win, idx) => {
                const winLvl = getLevelConfig(win.level);
                const sText = formatHour(win.start_hour, language);
                const eText = formatHour(win.end_hour, language);
                return (
                  <div key={idx} className="window-item">
                    <div>
                      <div className="window-time">
                        {language === 'hi' ? `${sText} से ${eText} तक` : `From ${sText} to ${eText}`}
                      </div>
                      <div className="window-work-ratio">
                        {language === 'hi'
                          ? `काम ${win.max_work_min} मिनट, आराम ${win.min_rest_min} मिनट प्रति घंटा`
                          : `Work ${win.max_work_min} min/hr, Rest ${win.min_rest_min} min/hr in shade`}
                      </div>
                    </div>
                    <span
                      className="risk-level-badge"
                      style={{
                        backgroundColor: winLvl.bg,
                        color: winLvl.text,
                        fontSize: '0.74rem'
                      }}
                    >
                      {winLvl.symbol}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
              No elevated heat-stress windows today. Conditions remain within normal limits all day.
            </p>
          )}
        </section>

        {/* Message for Supervisor */}
        <section className="card message-card" aria-labelledby="message-heading">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <h2 id="message-heading" className="card-title" style={{ margin: 0 }}>
                Supervisor Dispatch Message
              </h2>
              <span className="badge-tag">{language.toUpperCase()}</span>
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)', marginBottom: '0.75rem' }}>
              Automated Telegram text & voice dispatch sent to site supervisor:
            </p>
            <div className="message-text-box">
              {activeMessage}
            </div>
          </div>

          <button
            type="button"
            className="copy-btn"
            onClick={() => handleCopyMessage(activeMessage)}
            aria-label="Copy supervisor message to clipboard"
          >
            {copied ? '✓ Copied Message' : 'Copy Message Text'}
          </button>
        </section>
      </div>
    </div>
  );
}
