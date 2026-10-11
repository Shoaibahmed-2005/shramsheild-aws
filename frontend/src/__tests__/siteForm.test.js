import { describe, expect, it } from 'vitest';
import { DEFAULT_SITE_FORM, toSitePayload, validateSiteForm } from '../siteForm.js';

describe('site form validation', () => {
  it('accepts a site that follows contract section 3.3', () => {
    expect(validateSiteForm({ ...DEFAULT_SITE_FORM, name: 'Anna Nagar tower site', site_id: 'chn-01' })).toEqual({});
  });

  it('reports invalid site details', () => {
    const errors = validateSiteForm({
      ...DEFAULT_SITE_FORM,
      site_id: 'Too long!',
      name: '',
      lat: '5.9',
      lon: '98.1',
      workload: 'office',
      language: 'ta',
      acclimatized: 'yes',
      work_start_hour: '18',
      work_end_hour: '7',
      ack_timeout_seconds: '20',
    });
    expect(errors).toMatchObject({
      site_id: expect.any(String), name: expect.any(String), lat: expect.any(String), lon: expect.any(String),
      workload: expect.any(String), language: expect.any(String), acclimatized: expect.any(String), work_end_hour: expect.any(String),
      ack_timeout_seconds: expect.any(String),
    });
  });

  it('creates the contract payload without a Telegram chat-id field in the form', () => {
    const payload = toSitePayload({ ...DEFAULT_SITE_FORM, name: 'Test worksite', site_id: 'test-01' });
    expect(payload).toMatchObject({
      site_id: 'test-01', name: 'Test worksite', lat: 13.085, lon: 80.2101,
      supervisor: { telegram_chat_id: null }, backup: { telegram_chat_id: null },
    });
  });
});
