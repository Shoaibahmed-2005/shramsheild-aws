import { describe, it, expect } from 'vitest';
import { LEVELS } from '../levels.js';
import {
  formatHourEn,
  formatHourHi,
  formatHour,
  buildBacktestHeadline,
  getContrastRatio
} from '../utils.js';
import backtestFixture from '../fixtures/backtest.json';

describe('Level color contrast (WCAG AA requirement >= 4.5)', () => {
  const levels = Object.values(LEVELS);

  levels.forEach((level) => {
    it(`level ${level.key} (${level.symbol}) contrast ratio must be >= 4.5:1`, () => {
      const ratio = getContrastRatio(level.bg, level.text);
      expect(ratio).toBeGreaterThanOrEqual(4.5);
    });
  });
});

describe('Hour formatting (contract section 3.8)', () => {
  it('formats hours in English 12-hour format correctly', () => {
    expect(formatHourEn(0)).toBe('12 AM');
    expect(formatHourEn(9)).toBe('9 AM');
    expect(formatHourEn(12)).toBe('12 PM');
    expect(formatHourEn(17)).toBe('5 PM');
    expect(formatHourEn(23)).toBe('11 PM');
  });

  it('formats hours in Hindi according to time-of-day conventions', () => {
    // contract section 3.8 examples:
    // 9 gives "सुबह 9 बजे"
    // 12 gives "दोपहर 12 बजे"
    // 17 gives "शाम 5 बजे"
    // 0 gives "रात 12 बजे"
    expect(formatHourHi(0)).toBe('रात 12 बजे');
    expect(formatHourHi(9)).toBe('सुबह 9 बजे');
    expect(formatHourHi(12)).toBe('दोपहर 12 बजे');
    expect(formatHourHi(17)).toBe('शाम 5 बजे');
    expect(formatHourHi(2)).toBe('रात 2 बजे');
    expect(formatHourHi(7)).toBe('सुबह 7 बजे');
    expect(formatHourHi(14)).toBe('दोपहर 2 बजे');
    expect(formatHourHi(20)).toBe('रात 8 बजे');
  });

  it('formats by language code', () => {
    expect(formatHour(14, 'en')).toBe('2 PM');
    expect(formatHour(14, 'hi')).toBe('दोपहर 2 बजे');
  });
});

describe('Backtest headline sentence generation', () => {
  it('builds the exact expected sentence for backtestFixture', () => {
    const headline = buildBacktestHeadline(backtestFixture);
    expect(headline).toBe(
      'Between 1 April and 30 June 2024, 2097 work hours were RED or STOP across 4 cities. An air-temperature alert at 40 C would have missed 1864 of them (88.9%).'
    );
  });

  it('handles custom synthetic data', () => {
    const custom = {
      sites: [{ site_id: 'chn-01' }, { site_id: 'del-01' }],
      totals: {
        dangerous_hours: 500,
        by_threshold: [
          { threshold_c: 40, missed: 400, missed_pct: 80.0 }
        ]
      }
    };
    const headline = buildBacktestHeadline(custom);
    expect(headline).toBe(
      'Between 1 April and 30 June 2024, 500 work hours were RED or STOP across 2 cities. An air-temperature alert at 40 C would have missed 400 of them (80.0%).'
    );
  });
});
