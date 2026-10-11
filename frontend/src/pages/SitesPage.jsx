import React, { useState, useEffect } from 'react';
import { listSites } from '../api.js';
import { formatHourEn } from '../utils.js';

export function SitesPage() {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSitesData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await listSites();
      setSites(res.sites || []);
    } catch (err) {
      setError(err.message || 'Failed to load sites');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSitesData();
  }, []);

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Worksite Heat Safety Overview</h1>
          <p className="page-desc">Monitored outdoor worksites with daily WBGT heat-stress screening.</p>
        </div>
        <div className="sites-grid" aria-busy="true" aria-label="Loading worksites">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card skeleton skeleton-card" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-card" role="alert">
        <h2 className="error-title">Unable to Load Worksites</h2>
        <p className="error-msg">{error}</p>
        <button type="button" className="btn-retry" onClick={fetchSitesData}>
          Retry Loading
        </button>
      </div>
    );
  }

  if (sites.length === 0) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Worksite Heat Safety Overview</h1>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ color: 'var(--text-muted)' }}>No outdoor worksites configured.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Worksite Heat Safety Overview</h1>
        <p className="page-desc">
          Monitoring {sites.length} outdoor worksites. Select a site to view its 24-hour WBGT screening plan.
        </p>
      </div>

      <div className="sites-grid">
        {sites.map((site) => {
          const startText = formatHourEn(site.work_start_hour);
          const endText = formatHourEn(site.work_end_hour);
          const hoursDisplay = `${startText} - ${endText}`;
          const langDisplay = site.language === 'hi' ? 'Hindi (hi)' : 'English (en)';

          return (
            <article key={site.site_id} className="card site-card">
              <div>
                <div className="site-card-header">
                  <h2 className="site-name">{site.name}</h2>
                  <span className="site-id-badge">{site.site_id}</span>
                </div>
                <p style={{ fontSize: '0.84rem', color: 'var(--text-tertiary)' }}>
                  Lat {site.lat.toFixed(3)}°, Lon {site.lon.toFixed(3)}°
                </p>

                <div className="site-meta-list">
                  <div className="meta-item">
                    <span className="meta-label">Workload</span>
                    <span className="meta-value">{site.workload}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Acclimatized</span>
                    <span className="meta-value">{site.acclimatized ? 'Yes' : 'No'}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Work Hours</span>
                    <span className="meta-value">{hoursDisplay}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Alert Language</span>
                    <span className="meta-value">{langDisplay}</span>
                  </div>
                </div>
              </div>

              <a
                href={`#/site/${site.site_id}`}
                className="btn-view-plan"
                aria-label={`View daily heat plan for ${site.name}`}
              >
                View Heat Plan &rarr;
              </a>
            </article>
          );
        })}
      </div>
    </div>
  );
}
