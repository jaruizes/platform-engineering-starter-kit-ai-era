import { ReactNode, useState } from 'react';
import {
  Content,
  InfoCard,
  Progress,
  ResponseErrorPanel,
} from '@backstage/core-components';
import { fetchApiRef, useApi } from '@backstage/frontend-plugin-api';
import {
  Box,
  Button,
  Chip,
  Grid,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@material-ui/core';
import useAsyncRetry from 'react-use/esm/useAsyncRetry';
import useInterval from 'react-use/esm/useInterval';
import type { Approval, Overview } from '../types';

const ago = (iso: string) => {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
};

const until = (iso: string) => {
  const h = Math.round((new Date(iso).getTime() - Date.now()) / 3600000);
  return h <= 0 ? 'expiring' : `in ${h}h`;
};

const Requester = ({ type, name }: { type?: string; name?: string }) => (
  <>
    <Chip
      size="small"
      label={type === 'agent' ? 'agent' : 'human'}
      color={type === 'agent' ? 'secondary' : 'default'}
    />{' '}
    {name ?? '-'}
  </>
);

const Rows = ({
  columns,
  empty,
  children,
}: {
  columns: string[];
  empty: string;
  children: ReactNode[];
}) =>
  children.length === 0 ? (
    <Typography color="textSecondary">{empty}</Typography>
  ) : (
    <Table size="small">
      <TableHead>
        <TableRow>
          {columns.map(c => (
            <TableCell key={c}>{c}</TableCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>{children}</TableBody>
    </Table>
  );

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
  const environment = !r.kind || r.kind === 'Environment';
  return (
    <Box mb={2} p={2} border={1} borderColor="divider" borderRadius={8}>
      <Typography variant="subtitle1">
        <Chip size="small" label="agent" color="secondary" /> <b>{approval.agent}</b> asks for a{' '}
        {environment ? (
          <>
            <b>{r.size}</b> environment <b>{r.name}</b> for team <b>{r.team}</b>, {r.ttlHours}h
          </>
        ) : (
          <>
            <b>{r.size ?? ''}</b> {r.kind} <b>{r.name}</b> in <b>{r.namespace}</b>
          </>
        )}
      </Typography>
      {r.purpose && (
        <Typography variant="body2" color="textSecondary">
          Purpose: {r.purpose}
        </Typography>
      )}
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

  const { metrics: m, environments, apps, approvals, activity } = overview.value;
  const costs = Object.entries(m.cost_by_team).sort((a, b) => b[1] - a[1]);
  const maxCost = Math.max(...costs.map(([, cost]) => cost), 0.01);
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
        <Grid item xs={12}>
          <InfoCard title="Environments">
            <Rows
              columns={[
                'Name',
                'Team',
                'Size',
                'Requested by',
                'Approved by',
                '€/day',
                'Expires',
                'Status',
              ]}
              empty="No environments."
            >
              {environments.map(e => (
                <TableRow key={e.name}>
                  <TableCell>
                    <b>{e.name}</b>
                    <Typography variant="body2" color="textSecondary">
                      {e.purpose}
                    </Typography>
                  </TableCell>
                  <TableCell>{e.team}</TableCell>
                  <TableCell>{e.size}</TableCell>
                  <TableCell>
                    <Requester type={e.requester_type} name={e.requested_by} />
                  </TableCell>
                  <TableCell>{e.approved_by ?? '-'}</TableCell>
                  <TableCell>{e.estimated_daily_cost_eur.toFixed(2)}</TableCell>
                  <TableCell>{until(e.expires_at)}</TableCell>
                  <TableCell>{e.ready ? 'Ready' : 'Creating'}</TableCell>
                </TableRow>
              ))}
            </Rows>
          </InfoCard>
        </Grid>
        <Grid item xs={12} md={8}>
          <InfoCard title="Services">
            <Rows
              columns={['Service', 'Environment', 'Requested by', 'Status']}
              empty="No services."
            >
              {apps.map(a => (
                <TableRow key={`${a.namespace}/${a.name}`}>
                  <TableCell>
                    <b>{a.name}</b>
                    <Typography variant="body2" color="textSecondary">
                      {a.image || 'Waiting for the first image'}
                    </Typography>
                  </TableCell>
                  <TableCell>{a.namespace}</TableCell>
                  <TableCell>
                    <Requester type={a.requester_type} name={a.requested_by} />
                  </TableCell>
                  <TableCell>{a.ready ? 'Running' : 'Starting'}</TableCell>
                </TableRow>
              ))}
            </Rows>
          </InfoCard>
        </Grid>
        <Grid item xs={12} md={4}>
          <InfoCard title="Estimated cost per team (EUR/day)">
            {costs.length === 0 && <Typography color="textSecondary">Nothing running.</Typography>}
            {costs.map(([team, cost]) => (
              <Box key={team} mb={2}>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">{team}</Typography>
                  <Typography variant="body2">
                    <b>€{cost.toFixed(2)}</b>
                  </Typography>
                </Box>
                <LinearProgress variant="determinate" value={(cost / maxCost) * 100} />
              </Box>
            ))}
          </InfoCard>
        </Grid>
      </Grid>
    </Content>
  );
};
