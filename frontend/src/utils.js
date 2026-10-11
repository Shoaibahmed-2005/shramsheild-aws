/**
 * ShramShield Pure Formatting and Utility Functions
 * Follows contract: docs/BUILD_PLAN.md sections 3.2, 3.8, and 3.13
 */

export const DISCLAIMER_TEXT =
  'Screening guidance estimated from weather-model data. It is not a measurement or medical advice. Use on-site judgement and stop work if anyone feels unwell.';

/**
 * Format an hour number (0-23) in English 12-hour clock format.
 * Examples: 0 -> "12 AM", 9 -> "9 AM", 12 -> "12 PM", 17 -> "5 PM"
 */
export function formatHourEn(hour) {
  const h = Number(hour);
  if (isNaN(h) || h < 0 || h > 23) return '';
  if (h === 0) return '12 AM';
  if (h < 12) return `${h} AM`;
  if (h === 12) return '12 PM';
  return `${h - 12} PM`;
}

/**
 * Format an hour number (0-23) in Hindi time period format.
 * Rules from contract section 3.8:
 * - 0 to 3: "रात"
 * - 4 to 11: "सुबह"
 * - 12 to 15: "दोपहर"
 * - 16 to 18: "शाम"
 * - 19 to 23: "रात"
 * followed by 12-hour number and " बजे".
 * Examples: 9 -> "सुबह 9 बजे", 12 -> "दोपहर 12 बजे", 17 -> "शाम 5 बजे", 0 -> "रात 12 बजे"
 */
export function formatHourHi(hour) {
  const h = Number(hour);
  if (isNaN(h) || h < 0 || h > 23) return '';

  let prefix;
  if (h >= 0 && h <= 3) {
    prefix = 'रात';
  } else if (h >= 4 && h <= 11) {
    prefix = 'सुबह';
  } else if (h >= 12 && h <= 15) {
    prefix = 'दोपहर';
  } else if (h >= 16 && h <= 18) {
    prefix = 'शाम';
  } else {
    prefix = 'रात';
  }

  const num = h === 0 || h === 12 ? 12 : h % 12;
  return `${prefix} ${num} बजे`;
}

/**
 * Format hour by language.
 */
export function formatHour(hour, lang = 'en') {
  return lang === 'hi' ? formatHourHi(hour) : formatHourEn(hour);
}

/**
 * Generate headline sentence for the Backtest page.
 * Task P3.1 step 9:
 * "Between 1 April and 30 June 2024, N work hours were RED or STOP across 4 cities. An air-temperature alert at 40 C would have missed M of them (P%)."
 */
export function buildBacktestHeadline(backtest) {
  if (!backtest || !backtest.totals) {
    return 'Between 1 April and 30 June 2024, 0 work hours were RED or STOP across 4 cities.';
  }

  const n = backtest.totals.dangerous_hours ?? 0;
  const numCities = backtest.sites ? backtest.sites.length : 4;

  const threshold40 = (backtest.totals.by_threshold || []).find(
    (item) => item.threshold_c === 40
  );

  const m = threshold40 ? threshold40.missed : 0;
  const p = threshold40
    ? typeof threshold40.missed_pct === 'number'
      ? threshold40.missed_pct.toFixed(1)
      : threshold40.missed_pct
    : '0.0';

  return `Between 1 April and 30 June 2024, ${n} work hours were RED or STOP across ${numCities} cities. An air-temperature alert at 40 C would have missed ${m} of them (${p}%).`;
}

/**
 * WCAG Relative Luminance calculation for a hex color code.
 */
export function getRelativeLuminance(hexColor) {
  const hex = hexColor.replace('#', '').trim();
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  const toLinear = (c) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);

  const rLin = toLinear(r);
  const gLin = toLinear(g);
  const bLin = toLinear(b);

  return 0.2126 * rLin + 0.7152 * gLin + 0.0722 * bLin;
}

/**
 * WCAG 2.1 Contrast Ratio between two hex colors.
 */
export function getContrastRatio(hex1, hex2) {
  const l1 = getRelativeLuminance(hex1);
  const l2 = getRelativeLuminance(hex2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}
