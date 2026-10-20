import { useState } from 'react';
import {
  Content,
  InfoCard,
  Progress,
  ResponseErrorPanel,
} from '@backstage/core-components';
import { fetchApiRef, useApi } from '@backstage/frontend-plugin-api';
import { Box, Button, Chip, Grid, Typography } from '@material-ui/core';
import useAsyncRetry from 'react-use/esm/useAsyncRetry';
import useInterval from 'react-use/esm/useInterval';
import type { Approval, Overview } from '../types';

const ago = (iso: string) => {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
};

const Tile = ({ value, label }: { value: string | number; label: string }) => (
  <Grid item xs={6} md={2}>
    <InfoCard noPadding>
      <Box p={2}>
        <Typography variant="h4">{value}</Typography>
        <Typography variant="body2" color="textSecondary">
          {label}
        </Typography>
      </Box>
    </InfoCard>
  </Grid>
);

const PendingApproval = ({
  approval,
  onDecide,
}: {
  approval: Approval;
  onDecide: (id: string, decision: 'approve' | 'reject') => Promise<void>;
}) => {
  const [busy, setBusy] = useState(false);
  const decide = async (decision: 'approve' | 'reject') => {
    setBusy(true);
    try {
      await onDecide(approval.id, decision);
    } finally {
      setBusy(false);
    }
  };
  const r = approval.request;
  return (
    <Box mb={2} p={2} border={1} borderColor="divider" borderRadius={8}>
      <Typography variant="subtitle1">
        <Chip size="small" label="agent" color="secondary" /> <b>{approval.agent}</b> asks for a{' '}
        <b>{r.size}</b> environment <b>{r.name}</b> for team <b>{r.team}</b>, {r.ttlHours}h
      </Typography>
      <Typography variant="body2" color="textSecondary">
        Purpose: {r.purpose}
      </Typography>
      <Typography variant="body2" color="textSecondary" gutterBottom>
        Guardrail: {approval.reason}
      </Typography>
      <Button
        variant="contained"
        color="primary"
        disabled={busy}
        onClick={() => decide('approve')}
      >
        Approve
      </Button>{' '}
      <Button variant="outlined" disabled={busy} onClick={() => decide('reject')}>
        Reject
      </Button>
    </Box>
  );
};

export const AiPlatformPage = () => {
  const { fetch } = useApi(fetchApiRef);
  const [error, setError] = useState<string>();

  const overview = useAsyncRetry(async (): Promise<Overview> => {
    const res = await fetch('plugin://platform/overview');
    if (!res.ok) throw new Error(`The platform answered ${res.status} ${res.statusText}`);
    return res.json();
  }, [fetch]);
  useInterval(overview.retry, 5000);

  const decide = async (id: string, decision: 'approve' | 'reject') => {
    setError(undefined);
    const res = await fetch(`plugin://platform/approvals/${encodeURIComponent(id)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision }),
    });
    if (!res.ok) setError((await res.json()).error?.message ?? res.statusText);
    overview.retry();
  };

  if (!overview.value) {
    if (overview.error) return <ResponseErrorPanel error={overview.error} />;
    return <Progress />;
  }

  const { metrics: m, approvals, activity } = overview.value;
  const pending = approvals.filter(a => a.status === 'pending');
  const decided = approvals.filter(a => a.status !== 'pending').slice(0, 5);
  const pass = m.agent_first_time_pass_rate === null ? '-' : `${m.agent_first_time_pass_rate}%`;

  return (
    <Content>
      <Grid container spacing={2}>
        <Tile value={m.active_environments} label="Active environments" />
        <Tile value={`${m.agent_share}%`} label="Environments requested by agents" />
        <Tile value={pass} label="Agent requests passing guardrails first time" />
        <Tile value={m.denied_by_policy} label="Agent requests caught by policy" />
        <Tile value={m.pending_approvals} label="Waiting for a human decision" />
        <Tile
          value={`€${m.daily_cost_eur.toFixed(2)}`}
          label={`Cost per day (€${m.agent_daily_cost_eur.toFixed(2)} from agents)`}
        />
        <Grid item xs={12} md={7}>
          <InfoCard title="Agent requests waiting for a human decision">
            {error && (
              <Typography color="error" gutterBottom>
                {error}
              </Typography>
            )}
            {pending.length === 0 && (
              <Typography color="textSecondary">
                No requests waiting. Agents are staying inside the guardrails.
              </Typography>
            )}
            {pending.map(a => (
              <PendingApproval key={a.id} approval={a} onDecide={decide} />
            ))}
            {decided.length > 0 && (
              <Typography variant="body2" color="textSecondary">
                Recent decisions:{' '}
                {decided
                  .map(a => `${a.request.name} ${a.status} by ${a.decided_by ?? '-'}`)
                  .join(' · ')}
              </Typography>
            )}
          </InfoCard>
        </Grid>
        <Grid item xs={12} md={5}>
          <InfoCard title="Activity">
            {activity.length === 0 && <Typography color="textSecondary">Nothing yet.</Typography>}
            {activity.slice(0, 12).map((a, i) => (
              <Box key={i} mb={1}>
                <Typography variant="caption" color="textSecondary">
                  {ago(a.time)} · {a.component.replace('platform-', '')}
                </Typography>
                <Typography variant="body2" color={a.warning ? 'error' : 'textPrimary'}>
                  {a.message}
                </Typography>
              </Box>
            ))}
          </InfoCard>
        </Grid>
      </Grid>
    </Content>
  );
};
