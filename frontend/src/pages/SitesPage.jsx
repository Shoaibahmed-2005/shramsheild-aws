import React, { useCallback, useEffect, useState } from 'react';
import { createSite, listSites } from '../api.js';
import { DEFAULT_SITE_FORM, toSitePayload, validateSiteForm } from '../siteForm.js';
import { formatHourEn } from '../utils.js';

function FieldError({ message }) {
  return message ? <p className="form-error" role="alert">{message}</p> : null;
}

export function SitesPage() {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(DEFAULT_SITE_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [formMessage, setFormMessage] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchSitesData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await listSites();
      setSites(res.sites || []);
    } catch (requestError) {
      setError(requestError.message || 'Failed to load sites');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSitesData();
  }, [fetchSitesData]);

  const updateForm = (event) => {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
  };

  const submitSite = async (event) => {
    event.preventDefault();
    const validation = validateSiteForm(form);
    setFormErrors(validation);
    setFormMessage(null);
    if (Object.keys(validation).length) return;

    try {
      setSubmitting(true);
      const created = await createSite(toSitePayload(form));
      setForm(DEFAULT_SITE_FORM);
      setFormMessage(`Added ${created.name}.`);
      await fetchSitesData();
    } catch (requestError) {
      setFormMessage(requestError.message || 'Unable to add this site.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Worksite Heat Safety Overview</h1>
        <p className="page-desc">Monitored outdoor worksites with daily WBGT heat-stress screening.</p>
      </div>

      <section className="card site-form-card" aria-labelledby="add-site-heading">
        <h2 id="add-site-heading" className="card-title">Add worksite</h2>
        <p className="site-form-help">Set site details for weather-model screening. Contact chat IDs are configured separately.</p>
        <form className="site-form" onSubmit={submitSite} noValidate>
          <label>
            Site name
            <input name="name" value={form.name} onChange={updateForm} maxLength="60" aria-describedby="site-name-error" required />
            <FieldError message={formErrors.name} />
          </label>
          <label>
            Site ID (optional)
            <input name="site_id" value={form.site_id} onChange={updateForm} pattern="[a-z0-9-]{3,20}" aria-describedby="site-id-error" />
            <span className="field-hint">Lowercase letters, numbers, and hyphens; leave blank to generate one.</span>
            <FieldError message={formErrors.site_id} />
          </label>
          <label>
            Latitude
            <input name="lat" type="number" value={form.lat} onChange={updateForm} min="6" max="37" step="0.0001" required />
            <FieldError message={formErrors.lat} />
          </label>
          <label>
            Longitude
            <input name="lon" type="number" value={form.lon} onChange={updateForm} min="68" max="98" step="0.0001" required />
            <FieldError message={formErrors.lon} />
          </label>
          <label>
            Workload
            <select name="workload" value={form.workload} onChange={updateForm}>
              <option value="light">Light</option>
              <option value="moderate">Moderate</option>
              <option value="heavy">Heavy</option>
              <option value="very_heavy">Very heavy</option>
            </select>
            <FieldError message={formErrors.workload} />
          </label>
          <label>
            Work start hour (India time)
            <input name="work_start_hour" type="number" value={form.work_start_hour} onChange={updateForm} min="0" max="23" step="1" required />
            <FieldError message={formErrors.work_start_hour} />
          </label>
          <label>
            Work end hour (exclusive)
            <input name="work_end_hour" type="number" value={form.work_end_hour} onChange={updateForm} min="1" max="24" step="1" required />
            <FieldError message={formErrors.work_end_hour} />
          </label>
          <label>
            Alert language
            <select name="language" value={form.language} onChange={updateForm}>
              <option value="hi">Hindi</option>
              <option value="en">English</option>
            </select>
            <FieldError message={formErrors.language} />
          </label>
          <label>
            Acknowledgement timeout (seconds)
            <input name="ack_timeout_seconds" type="number" value={form.ack_timeout_seconds} onChange={updateForm} min="30" max="3600" step="1" required />
            <FieldError message={formErrors.ack_timeout_seconds} />
          </label>
          <label className="checkbox-field">
            <input name="acclimatized" type="checkbox" checked={form.acclimatized} onChange={updateForm} />
            <span>Workers are acclimatized to heat</span>
          </label>
          <div className="site-form-actions">
            <button className="btn-view-plan" type="submit" disabled={submitting}>
              {submitting ? 'Adding site…' : 'Add site'}
            </button>
            {formMessage && <p className="form-message" role="status">{formMessage}</p>}
          </div>
        </form>
      </section>

      {loading && (
        <div className="sites-grid" aria-busy="true" aria-label="Loading worksites">
          {[1, 2, 3, 4].map((index) => <div key={index} className="card skeleton skeleton-card" />)}
        </div>
      )}

      {!loading && error && (
        <div className="error-card" role="alert">
          <h2 className="error-title">Unable to Load Worksites</h2>
          <p className="error-msg">{error}</p>
          <button type="button" className="btn-retry" onClick={fetchSitesData}>Retry Loading</button>
        </div>
      )}

      {!loading && !error && sites.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ color: 'var(--text-muted)' }}>No outdoor worksites configured.</p>
        </div>
      )}

      {!loading && !error && sites.length > 0 && (
        <div className="sites-grid">
          {sites.map((site) => {
            const hoursDisplay = `${formatHourEn(site.work_start_hour)} - ${formatHourEn(site.work_end_hour)}`;
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
                    <div className="meta-item"><span className="meta-label">Workload</span><span className="meta-value">{site.workload}</span></div>
                    <div className="meta-item"><span className="meta-label">Acclimatized</span><span className="meta-value">{site.acclimatized ? 'Yes' : 'No'}</span></div>
                    <div className="meta-item"><span className="meta-label">Work Hours</span><span className="meta-value">{hoursDisplay}</span></div>
                    <div className="meta-item"><span className="meta-label">Alert Language</span><span className="meta-value">{langDisplay}</span></div>
                  </div>
                </div>
                <a href={`#/site/${site.site_id}`} className="btn-view-plan" aria-label={`View daily heat plan for ${site.name}`}>View Heat Plan →</a>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
