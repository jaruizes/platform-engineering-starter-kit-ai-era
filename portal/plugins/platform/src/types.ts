export type Approval = {
  id: string;
  status: 'pending' | 'approved' | 'rejected' | 'failed';
  agent: string;
  reason: string;
  decided_by?: string;
  decision_note?: string;
  request: { name: string; team: string; size: string; ttlHours: number; purpose: string };
  created_at: string;
};

export type Activity = {
  time: string;
  component: string;
  action: string;
  subject: string;
  message: string;
  actor: string;
  warning: boolean;
};

export type Metrics = {
  active_environments: number;
  agent_share: number;
  agent_requests: number;
  agent_first_time_pass_rate: number | null;
  denied_by_policy: number;
  pending_approvals: number;
  daily_cost_eur: number;
  agent_daily_cost_eur: number;
  cost_by_team: Record<string, number>;
};

export type Overview = { metrics: Metrics; approvals: Approval[]; activity: Activity[] };
