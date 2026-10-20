/**
 * Client for the platform console, which holds the human approvals for
 * agent requests and the AI-era metrics. The portal shows them and lets
 * signed-in people decide, but the decision is still made by the console's
 * approver identity, so the guardrails stay in one place.
 */
export type ConsoleState = {
  environments: Array<Record<string, any>>;
  apps: Array<Record<string, any>>;
  approvals: Array<{
    id: string;
    status: string;
    agent: string;
    reason: string;
    decided_by?: string;
    decision_note?: string;
    request: { name: string; team: string; size: string; ttlHours: number; purpose: string };
    created_at: string;
  }>;
  activity: Array<Record<string, any>>;
  metrics: Record<string, any>;
};

export class ConsoleClient {
  constructor(private readonly baseUrl: string) {}

  async state(): Promise<ConsoleState> {
    const res = await fetch(`${this.baseUrl}/api/state`);
    if (!res.ok) {
      throw new Error(`Platform console answered ${res.status}`);
    }
    return (await res.json()) as ConsoleState;
  }

  async decide(id: string, decision: 'approve' | 'reject', approver: string) {
    const res = await fetch(`${this.baseUrl}/api/approvals/${encodeURIComponent(id)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, approver }),
    });
    const body = await res.json();
    return { status: res.status, body };
  }
}
