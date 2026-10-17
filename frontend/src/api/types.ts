/**
 * MuleTrace API Schema Types
 * Matched strictly to backend/api/models.py and OpenAPI spec
 */

export interface HealthStatus {
  status: 'ok' | 'degraded';
  falkordb_reachable: boolean;
  groq_key_present: boolean;
  mcp_mode: string;
  graph_node_count?: number;
  graph_nodes_count?: number;
  saved_cases_count?: number;
}

export interface FraudReport {
  id: string;
  victim_account: string;
  amount: number;
  reported_at: number;
  description: string;
}

export interface ToolInfo {
  name: string;
  kind: 'query' | 'algorithm' | 'action' | 'trace' | 'ledger' | 'freeze' | 'memory';
  short_description: string;
  description?: string;
  parameters?: Record<string, any>;
  when_to_use?: string;
  when_not_to_use?: string;
}

export interface InvestigationStartRequest {
  report_id?: string;
  task?: string;
  save_memory?: boolean;
  polish?: boolean;
  mode?: 'live' | 'replay';
  speed?: number;
}

export interface InvestigationStartResponse {
  session_id: string;
  status: 'running' | 'done' | 'error';
  mode: 'live' | 'replay';
  replay: boolean;
  fallback_available: boolean;
}

export interface AgentEvent {
  type: 'thought' | 'tool_call' | 'tool_result' | 'final' | 'error' | 'done';
  session_id?: string;
  call_id?: string;
  tool?: string;
  arguments?: Record<string, any>;
  content?: string;
  summary?: string;
  message?: string;
  details?: any;
  duration_ms?: number;
  // Final event payload
  case_id?: string;
  verified?: boolean;
  disclaimer?: string;
  total_recoverable?: number;
  recommendations_count?: number;
  rejections_count?: number;
}

export interface HighlightNode {
  id: string;
  role: 'victim' | 'mule_recommended' | 'cash_out' | 'cleared' | 'linked_ring' | 'shared_device' | 'other';
  label: string;
  bank?: string;
  balance?: number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface HighlightEdge {
  source: string | HighlightNode;
  target: string | HighlightNode;
  type: string;
  txn_id?: string | null;
  amount?: number | null;
  timestamp?: number | null;
  role: 'mule_recommended' | 'cash_out' | 'shared_device' | 'other';
  sequence_index?: number | null;
}

export interface HighlightGraph {
  nodes: HighlightNode[];
  edges: HighlightEdge[];
  legend: Record<string, string>;
  disclaimer: string;
}

export interface CaseHeader {
  case_id: string;
  session_id: string;
  report_id: string;
  victim_name: string;
  victim_account: string;
  amount_stolen?: number;
  stolen_amount?: number;
  reported_at?: number;
  total_recoverable: number;
  total_cashed_out?: number;
  recommendation_only: boolean;
  disclaimer?: string;
}

export interface RecommendationItem {
  account: string;
  priority: number;
  headline: string;
  path: string[];
  path_text: string;
  signals: Array<string | { name: string; plain_english?: string }>;
  money: {
    recoverable_balance: number;
    amount_cashed_out: number;
    stolen_attributable: number;
  };
  confidence: 'high' | 'medium' | 'low';
  steps: string[];
  counter_evidence?: string[];
  tool_calls: string[];
  bank?: string;
  disclaimer: string;
}

export interface RejectionItem {
  account: string;
  holder_name?: string;
  bank?: string;
  headline?: string;
  reasons: string[];
  signals?: Array<string | { name: string; plain_english?: string }>;
  behavioral_profile?: {
    distinct_senders?: number;
    forward_latency_seconds?: number;
    device_stability?: number;
    onward_ratio?: number;
  };
  why_insufficient?: string;
  disclaimer?: string;
}

export interface LinkedRingItem {
  account_a: string;
  account_b: string;
  shared_type: string;
  shared_id: string;
  total_sharers: number;
  strength: 'strong' | 'weak';
  strength_eval: string;
  first_seen?: number;
  last_seen?: number;
  path: string[];
  path_text: string;
  headline: string;
  explanation: string;
  disclaimer: string;
}

export interface TimelineStep {
  step: number;
  call_id: string;
  tool: string;
  purpose: string;
  key_result: string;
  duration_ms: number;
  duration: string;
  ok: boolean;
}

export interface CaseExplanation {
  case_header: CaseHeader;
  timeline: TimelineStep[];
  highlight: HighlightGraph;
  recommendations: RecommendationItem[];
  rejections: RejectionItem[];
  links: LinkedRingItem[];
  other_patterns: string[];
  limitations: string[];
  disclaimer: string;
  verified: boolean;
  verification?: {
    verified: boolean;
    checks: Record<string, any>;
    verified_at?: number;
  };
}

export interface InvestigationStatusResponse {
  session_id: string;
  status: 'running' | 'done' | 'error' | 'cancelled';
  mode: 'live' | 'replay';
  replay: boolean;
  verified?: boolean;
  case?: CaseExplanation;
  error?: string;
  disclaimer: string;
}

export interface SavedCaseSummary {
  session_id: string;
  report_id: string;
  case_id: string;
  victim_name: string;
  total_recoverable: number;
  recoverable_total?: number;
  verified: boolean;
  timestamp?: number;
  created_at?: number;
  status?: string;
  file?: string;
}

export interface AccountProfile {
  account_id: string;
  holder_name?: string;
  bank?: string;
  balance?: number;
  inflow?: number;
  outflow?: number;
  transaction_count?: number;
  distinct_senders?: number;
  distinct_recipients?: number;
  shared_device_count: number;
  shared_phone_count: number;
  connected_devices?: Array<{ id: string; share_count: number }>;
  connected_phones?: Array<{ id: string; share_count: number }>;
  first_seen?: number;
  last_seen?: number;
}

export interface ApiError {
  error: string;
  hint?: string;
}
