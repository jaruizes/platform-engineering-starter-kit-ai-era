import { InfoCard, StructuredMetadataTable } from '@backstage/core-components';
import { useEntity } from '@backstage/plugin-catalog-react';
import { Chip } from '@material-ui/core';

const PREFIX = 'platform.starterkit.dev';

/** Who asked for this through a Golden Path, who approved it and what it costs. */
export const PlatformRequestCard = () => {
  const { entity } = useEntity();
  const a = entity.metadata.annotations ?? {};
  const type = a[`${PREFIX}/requester-type`];
  const metadata: Record<string, any> = {
    'Requested by': (
      <>
        {type && (
          <Chip size="small" label={type} color={type === 'agent' ? 'secondary' : 'primary'} />
        )}{' '}
        {a[`${PREFIX}/requested-by`] ?? '-'}
      </>
    ),
    'Approved by': a[`${PREFIX}/approved-by`] ?? '-',
    Status: a[`${PREFIX}/status`] ?? '-',
  };
  if (entity.kind === 'Resource') {
    metadata.Size = a[`${PREFIX}/size`] ?? '-';
    metadata['Estimated cost'] = `${a[`${PREFIX}/estimated-daily-cost-eur`] ?? '-'} EUR/day`;
    metadata.Expires = a[`${PREFIX}/expires-at`]
      ? new Date(a[`${PREFIX}/expires-at`]).toLocaleString()
      : '-';
  }
  return (
    <InfoCard title="Golden Path request">
      <StructuredMetadataTable metadata={metadata} />
    </InfoCard>
  );
};
