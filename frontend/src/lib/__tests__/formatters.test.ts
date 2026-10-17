import { describe, it, expect } from 'vitest';
import {
  formatRupees,
  formatCompactRupees,
  formatExactIST,
  formatRelativeTime,
  formatElapsedOffset,
  formatDuration,
  formatAccountShort,
} from '../formatters';

describe('Formatters Unit Tests', () => {
  describe('formatRupees', () => {
    it('formats numbers with Indian comma grouping by default', () => {
      expect(formatRupees(85000)).toBe('₹85,000');
      expect(formatRupees(150000)).toBe('₹1,50,000');
      expect(formatRupees(10000000)).toBe('₹1,00,00,000');
    });

    it('supports custom prefix (e.g. Rs )', () => {
      expect(formatRupees(85000, 'Rs ')).toBe('Rs 85,000');
    });

    it('gracefully handles null, undefined, or NaN', () => {
      expect(formatRupees(null)).toBe('₹0');
      expect(formatRupees(undefined)).toBe('₹0');
      expect(formatRupees(NaN)).toBe('₹0');
    });
  });

  describe('formatCompactRupees', () => {
    it('formats thousands, lakhs, and crores', () => {
      expect(formatCompactRupees(500)).toBe('₹500');
      expect(formatCompactRupees(85000)).toBe('₹85.0K');
      expect(formatCompactRupees(250000)).toBe('₹2.5 L');
      expect(formatCompactRupees(15000000)).toBe('₹1.5 Cr');
    });
  });

  describe('formatExactIST', () => {
    it('formats timestamps in Indian Standard Time (IST)', () => {
      const ts = 1792044900; // in seconds
      const formatted = formatExactIST(ts);
      expect(formatted).toContain('IST');
    });

    it('handles zero or missing timestamp', () => {
      expect(formatExactIST(0)).toBe('—');
    });
  });

  describe('formatRelativeTime', () => {
    it('calculates human relative elapsed time', () => {
      const nowSec = Math.floor(Date.now() / 1000);
      expect(formatRelativeTime(nowSec - 2)).toBe('just now');
      expect(formatRelativeTime(nowSec - 30)).toBe('30s ago');
      expect(formatRelativeTime(nowSec - 300)).toBe('5m ago');
      expect(formatRelativeTime(nowSec - 7200)).toBe('2h ago');
    });
  });

  describe('formatElapsedOffset', () => {
    it('formats duration offsets since theft', () => {
      const base = 1000;
      expect(formatElapsedOffset(base, base + 45)).toBe('+45s');
      expect(formatElapsedOffset(base, base + 252)).toBe('+4m 12s');
    });
  });

  describe('formatDuration', () => {
    it('formats millisecond durations', () => {
      expect(formatDuration(450)).toBe('450ms');
      expect(formatDuration(2400)).toBe('2.4s');
    });
  });

  describe('formatAccountShort', () => {
    it('strips ACC_ prefix for clean display', () => {
      expect(formatAccountShort('ACC_0461')).toBe('0461');
      expect(formatAccountShort('ACC_0476')).toBe('0476');
    });
  });
});
