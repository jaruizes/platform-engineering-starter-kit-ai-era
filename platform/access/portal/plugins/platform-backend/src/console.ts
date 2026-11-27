/**
 * Client for the read-only platform console, for the agents' context actions
 * (team usage, pending approvals). People see and decide approvals through the
 * platform API with their own token (router.ts); the console decides nothing.
 */
export type ConsoleState = {
  environments: Array<Record<string, any>>;
  services: Array<Record<string, any>>;
  approvals: Array<{
    id: string;
    status: string;
    agent: string;
    reason: string;
    decided_by?: string;
    decision_note?: string;
    request: {
      name: string;
      kind?: string;
      namespace?: string;
      team?: string;
      size?: string;
      ttlHours?: number;
      purpose?: string;
    };
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
}
