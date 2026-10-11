const WORKLOADS = ['light', 'moderate', 'heavy', 'very_heavy'];
const LANGUAGES = ['hi', 'en'];
const SITE_ID_PATTERN = /^[a-z0-9-]{3,20}$/;

export const DEFAULT_SITE_FORM = {
  site_id: '',
  name: '',
  lat: '13.085',
  lon: '80.2101',
  workload: 'moderate',
  acclimatized: true,
  work_start_hour: '7',
  work_end_hour: '18',
  language: 'hi',
  ack_timeout_seconds: '900',
};

function numberValue(value) {
  return typeof value === 'number' ? value : Number(value);
}

/** Validate the browser form against the site rules in contract section 3.3. */
export function validateSiteForm(values) {
  const errors = {};
  const name = values.name?.trim() || '';
  const lat = numberValue(values.lat);
  const lon = numberValue(values.lon);
  const workStart = numberValue(values.work_start_hour);
  const workEnd = numberValue(values.work_end_hour);
  const timeout = numberValue(values.ack_timeout_seconds);
  const siteId = values.site_id?.trim() || '';

  if (!name) errors.name = 'Enter a site name.';
  else if (name.length > 60) errors.name = 'Site name must be 60 characters or fewer.';
  if (!Number.isFinite(lat) || lat < 6 || lat > 37) errors.lat = 'Latitude must be between 6 and 37.';
  if (!Number.isFinite(lon) || lon < 68 || lon > 98) errors.lon = 'Longitude must be between 68 and 98.';
  if (!WORKLOADS.includes(values.workload)) errors.workload = 'Choose a valid workload.';
  if (!LANGUAGES.includes(values.language)) errors.language = 'Choose Hindi or English.';
  if (typeof values.acclimatized !== 'boolean') errors.acclimatized = 'Choose whether workers are acclimatized.';
  if (!Number.isInteger(workStart) || workStart < 0 || workStart > 23) errors.work_start_hour = 'Work start must be an hour from 0 to 23.';
  if (!Number.isInteger(workEnd) || workEnd < 1 || workEnd > 24) errors.work_end_hour = 'Work end must be an hour from 1 to 24.';
  else if (Number.isInteger(workStart) && workEnd <= workStart) errors.work_end_hour = 'Work end must be later than work start.';
  if (!Number.isInteger(timeout) || timeout < 30 || timeout > 3600) errors.ack_timeout_seconds = 'Acknowledgement timeout must be 30 to 3600 seconds.';
  if (siteId && !SITE_ID_PATTERN.test(siteId)) errors.site_id = 'Site ID must use 3 to 20 lowercase letters, numbers, or hyphens.';
  return errors;
}

export function toSitePayload(values) {
  return {
    ...(values.site_id.trim() ? { site_id: values.site_id.trim() } : {}),
    name: values.name.trim(),
    lat: numberValue(values.lat),
    lon: numberValue(values.lon),
    workload: values.workload,
    acclimatized: Boolean(values.acclimatized),
    work_start_hour: numberValue(values.work_start_hour),
    work_end_hour: numberValue(values.work_end_hour),
    language: values.language,
    supervisor: { name: 'Supervisor', telegram_chat_id: null },
    backup: { name: 'Backup', telegram_chat_id: null },
    ack_timeout_seconds: numberValue(values.ack_timeout_seconds),
  };
}
