import {
  HealthStatus,
  FraudReport,
  ToolInfo,
  InvestigationStartRequest,
  InvestigationStartResponse,
  InvestigationStatusResponse,
  CaseExplanation,
  HighlightGraph,
  SavedCaseSummary,
  AccountProfile,
  ApiError,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL || '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorData: ApiError;
    try {
      errorData = await res.json();
    } catch {
      errorData = {
        error: `HTTP Error ${res.status}: ${res.statusText}`,
        hint: 'Verify server logs or network connectivity.',
      };
    }
    throw errorData;
  }
  return res.json();
}

export const api = {
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse<HealthStatus>(res);
  },

  async getReports(): Promise<FraudReport[]> {
    const res = await fetch(`${API_BASE}/api/reports`);
    return handleResponse<FraudReport[]>(res);
  },

  async getTools(): Promise<ToolInfo[]> {
    const res = await fetch(`${API_BASE}/api/tools`);
    return handleResponse<ToolInfo[]>(res);
  },

  async startInvestigation(req: InvestigationStartRequest): Promise<InvestigationStartResponse> {
    const res = await fetch(`${API_BASE}/api/investigations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse<InvestigationStartResponse>(res);
  },

  async getInvestigationStatus(sessionId: string): Promise<InvestigationStatusResponse> {
    const res = await fetch(`${API_BASE}/api/investigations/${encodeURIComponent(sessionId)}`);
    return handleResponse<InvestigationStatusResponse>(res);
  },

  async cancelInvestigation(sessionId: string): Promise<{ session_id: string; status: string }> {
    const res = await fetch(`${API_BASE}/api/investigations/${encodeURIComponent(sessionId)}/cancel`, {
      method: 'POST',
    });
    return handleResponse<{ session_id: string; status: string }>(res);
  },

  async getCases(): Promise<SavedCaseSummary[]> {
    const res = await fetch(`${API_BASE}/api/cases`);
    return handleResponse<SavedCaseSummary[]>(res);
  },

  async getCaseExplanation(sessionId: string, format: 'json' | 'markdown' | 'text' = 'json'): Promise<any> {
    const url = `${API_BASE}/api/cases/${encodeURIComponent(sessionId)}${format !== 'json' ? `?format=${format}` : ''}`;
    const res = await fetch(url);
    if (format === 'markdown' || format === 'text') {
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return res.text();
    }
    return handleResponse<CaseExplanation>(res);
  },

  async getCaseHighlight(sessionId: string): Promise<HighlightGraph> {
    const res = await fetch(`${API_BASE}/api/cases/${encodeURIComponent(sessionId)}/highlight`);
    return handleResponse<HighlightGraph>(res);
  },

  async getAccountProfile(accountId: string): Promise<AccountProfile> {
    const res = await fetch(`${API_BASE}/api/accounts/${encodeURIComponent(accountId)}`);
    return handleResponse<AccountProfile>(res);
  },

  async getNeighborhood(accountId: string, hops = 2, limit = 60): Promise<any> {
    const res = await fetch(
      `${API_BASE}/api/graph/neighborhood?account_id=${encodeURIComponent(accountId)}&hops=${hops}&limit=${limit}`
    );
    return handleResponse<any>(res);
  },

  async getMemoryCases(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/api/memory/cases`);
    return handleResponse<any[]>(res);
  },

  async resetMemory(): Promise<{ status: string; message: string }> {
    const res = await fetch(`${API_BASE}/api/admin/reset-memory`, {
      method: 'POST',
    });
    return handleResponse<{ status: string; message: string }>(res);
  },
};
