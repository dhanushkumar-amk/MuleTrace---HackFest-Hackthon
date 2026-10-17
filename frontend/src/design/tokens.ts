/**
 * MuleTrace Design System Tokens
 * Strict semantic color mappings, typography, radii, elevations, and motion curves.
 * Optimized for pristine, high-contrast, modern Light Theme.
 */

export const SEMANTIC_COLORS = {
  // Graph, badge, chip, and table role mapping (strict single source of truth)
  victim: {
    color: '#2563eb', // blue-600
    bg: '#eff6ff',    // blue-50
    border: '#bfdbfe', // blue-200
    text: '#1d4ed8',   // blue-700
    label: 'Victim',
  },
  mule_recommended: {
    color: '#dc2626', // red-600
    bg: '#fef2f2',    // red-50
    border: '#fecaca', // red-200
    text: '#b91c1c',   // red-700
    label: 'Freeze Recommended',
  },
  cash_out: {
    color: '#d97706', // amber-600
    bg: '#fffbeb',    // amber-50
    border: '#fde68a', // amber-200
    text: '#b45309',   // amber-700
    label: 'Cash-out Point',
  },
  cleared: {
    color: '#059669', // emerald-600
    bg: '#ecfdf5',    // emerald-50
    border: '#a7f3d0', // emerald-200
    text: '#047857',   // emerald-700
    label: 'Cleared Decoy',
  },
  linked_ring: {
    color: '#7c3aed', // violet-600
    bg: '#f5f3ff',    // violet-50
    border: '#ddd6fe', // violet-200
    text: '#6d28d9',   // violet-700
    label: 'Linked Ring',
  },
  shared_device: {
    color: '#0891b2', // cyan-600
    bg: '#ecfeff',    // cyan-50
    border: '#a5f3fc', // cyan-200
    text: '#0e7490',   // cyan-700
    label: 'Shared Device',
  },
  neutral: {
    color: '#64748b', // slate-500
    bg: '#f8fafc',    // slate-50
    border: '#e2e8f0', // slate-200
    text: '#334155',   // slate-700
    label: 'Pass-through',
  },
} as const;

export type SemanticRole = keyof typeof SEMANTIC_COLORS;

export const MOTION = {
  durations: {
    fast: 120,
    normal: 200,
    smooth: 320,
    deliberate: 600,
  },
  easings: {
    standard: [0.16, 1, 0.3, 1], // Apple-style spring ease-out
    accelerate: [0.4, 0, 1, 1],
    decelerate: [0, 0, 0.2, 1],
  },
} as const;

export const BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const;
