/**
 * MuleTrace Design System Tokens
 * Strict semantic color mappings, typography, radii, elevations, and motion curves.
 */

export const SEMANTIC_COLORS = {
  // Graph, badge, chip, and table role mapping (strict single source of truth)
  victim: {
    color: '#3b82f6', // blue-500
    bg: 'rgba(59, 130, 246, 0.12)',
    border: 'rgba(59, 130, 246, 0.28)',
    text: '#60a5fa',
    label: 'Victim',
  },
  mule_recommended: {
    color: '#f43f5e', // rose-500
    bg: 'rgba(244, 63, 94, 0.12)',
    border: 'rgba(244, 63, 94, 0.28)',
    text: '#fb7185',
    label: 'Freeze Recommended',
  },
  cash_out: {
    color: '#f59e0b', // amber-500
    bg: 'rgba(245, 158, 11, 0.12)',
    border: 'rgba(245, 158, 11, 0.28)',
    text: '#fbbf24',
    label: 'Cash-out Point',
  },
  cleared: {
    color: '#10b981', // emerald-500
    bg: 'rgba(16, 185, 129, 0.12)',
    border: 'rgba(16, 185, 129, 0.28)',
    text: '#34d399',
    label: 'Cleared Decoy',
  },
  linked_ring: {
    color: '#8b5cf6', // violet-500
    bg: 'rgba(139, 92, 246, 0.12)',
    border: 'rgba(139, 92, 246, 0.28)',
    text: '#a78bfa',
    label: 'Linked Ring',
  },
  shared_device: {
    color: '#06b6d4', // cyan-500
    bg: 'rgba(6, 182, 212, 0.12)',
    border: 'rgba(6, 182, 212, 0.28)',
    text: '#22d3ee',
    label: 'Shared Device',
  },
  neutral: {
    color: '#64748b', // slate-500
    bg: 'rgba(100, 116, 139, 0.12)',
    border: 'rgba(100, 116, 139, 0.28)',
    text: '#94a3b8',
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
