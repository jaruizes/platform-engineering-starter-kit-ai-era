import { InfoCard, Progress, ResponseErrorPanel } from '@backstage/core-components';
import { fetchApiRef, useApi } from '@backstage/frontend-plugin-api';
import { useEntity } from '@backstage/plugin-catalog-react';
import { Box, Chip, Typography } from '@material-ui/core';
import useAsync from 'react-use/esm/useAsync';

type QualityResult = {
  status: string;
  sourceCommit?: string;
  architecture?: string;
  profile?: { name: string; version: number };
  checks: Array<{ id?: string; status?: string; lineCoveragePercent?: number }>;
};

export const ServiceQualityCard = () => {
  const { entity } = useEntity();
  const { fetch } = useApi(fetchApiRef);
  const name = entity.metadata.name;
  const result = useAsync(async () => {
    const response = await fetch(`plugin://platform/quality/${encodeURIComponent(name)}`);
    if (!response.ok && response.status !== 404) throw new Error(`Quality service answered ${response.status}`);
    if (response.status === 404) return undefined;
    return (await response.json()) as QualityResult;
  }, [fetch, name]);

  if (result.loading) return <Progress />;
  if (result.error) return <ResponseErrorPanel error={result.error} />;
  const quality = result.value;
  if (!quality) {
    return <InfoCard title="Software quality"><Typography color="textSecondary">No committed quality evidence yet.</Typography></InfoCard>;
  }
  const passed = quality.status === 'passed';
  return (
    <InfoCard title="Software quality">
      <Box mb={1}>
        <Chip size="small" color={passed ? 'primary' : 'secondary'} label={passed ? 'Passing' : 'Failing'} />{' '}
        <Chip size="small" variant="outlined" label={quality.architecture ?? 'Unknown architecture'} />
      </Box>
      <Typography variant="body2" color="textSecondary">
        Profile {quality.profile?.name ?? '-'} v{quality.profile?.version ?? '-'} · commit {quality.sourceCommit?.slice(0, 12) ?? '-'}
      </Typography>
      {quality.checks.map(check => (
        <Typography key={check.id} variant="body2" color={check.status === 'failed' ? 'error' : 'textPrimary'}>
          {check.id}: {check.status}{check.lineCoveragePercent !== undefined ? ` · ${check.lineCoveragePercent}% line coverage` : ''}
        </Typography>
      ))}
    </InfoCard>
  );
};
