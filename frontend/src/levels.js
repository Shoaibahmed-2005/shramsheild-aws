/**
 * ShramShield Heat-Stress Levels and Display Properties
 * Source contract: docs/BUILD_PLAN.md sections 3.7 & 3.8, and task card P3.1 step 5
 */

export const LEVELS = {
  GREEN: {
    key: 'GREEN',
    name: {
      en: 'low',
      hi: 'कम'
    },
    bg: '#1b7f3b',
    text: '#ffffff',
    symbol: 'LOW',
    maxWorkMin: 60,
    minRestMin: 0,
    band: 'A (75-100% work)'
  },
  YELLOW: {
    key: 'YELLOW',
    name: {
      en: 'moderate',
      hi: 'मध्यम'
    },
    bg: '#f2c200',
    text: '#111111',
    symbol: 'MODERATE',
    maxWorkMin: 45,
    minRestMin: 15,
    band: 'B (50-75% work)'
  },
  ORANGE: {
    key: 'ORANGE',
    name: {
      en: 'high',
      hi: 'ज़्यादा'
    },
    bg: '#e8710a',
    text: '#111111',
    symbol: 'HIGH',
    maxWorkMin: 30,
    minRestMin: 30,
    band: 'C (25-50% work)'
  },
  RED: {
    key: 'RED',
    name: {
      en: 'very high',
      hi: 'बहुत ज़्यादा'
    },
    bg: '#c62828',
    text: '#ffffff',
    symbol: 'VERY HIGH',
    maxWorkMin: 15,
    minRestMin: 45,
    band: 'D (0-25% work)'
  },
  STOP: {
    key: 'STOP',
    name: {
      en: 'extreme',
      hi: 'अत्यधिक'
    },
    bg: '#5b0f12',
    text: '#ffffff',
    symbol: 'EXTREME',
    maxWorkMin: 0,
    minRestMin: 60,
    band: 'Stop non-essential work'
  },
  UNKNOWN: {
    key: 'UNKNOWN',
    name: {
      en: 'no data',
      hi: 'डेटा नहीं'
    },
    bg: '#6b7280',
    text: '#ffffff',
    symbol: 'NO DATA',
    maxWorkMin: null,
    minRestMin: null,
    band: 'Missing data'
  }
};

export function getLevelConfig(level) {
  if (!level || !LEVELS[level]) {
    return LEVELS.UNKNOWN;
  }
  return LEVELS[level];
}
