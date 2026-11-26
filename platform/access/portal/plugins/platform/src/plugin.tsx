import {
  createFrontendPlugin,
  PageBlueprint,
} from '@backstage/frontend-plugin-api';
import { EntityCardBlueprint } from '@backstage/plugin-catalog-react/alpha';
import SmartToyIcon from '@material-ui/icons/Memory';
import { rootRouteRef } from './routes';

/** AI-era platform view: agent approvals, metrics and activity. */
export const aiPlatformPage = PageBlueprint.make({
  params: {
    path: '/ai-platform',
    title: 'AI Platform',
    icon: <SmartToyIcon />,
    routeRef: rootRouteRef,
    loader: () => import('./components/AiPlatformPage').then(m => <m.AiPlatformPage />),
  },
});

/** Shows who requested an environment or service, and who approved it. */
export const platformRequestCard = EntityCardBlueprint.make({
  name: 'request',
  params: {
    filter: { 'metadata.annotations.platform.starterkit.dev/requester-type': { $exists: true } },
    loader: () =>
      import('./components/PlatformRequestCard').then(m => <m.PlatformRequestCard />),
  },
});

export const serviceQualityCard = EntityCardBlueprint.make({
  name: 'service-quality',
  params: {
    filter: { kind: 'Component', 'spec.type': 'service' },
    loader: () => import('./components/ServiceQualityCard').then(m => <m.ServiceQualityCard />),
  },
});

export const platformPlugin = createFrontendPlugin({
  pluginId: 'platform',
  extensions: [aiPlatformPage, platformRequestCard, serviceQualityCard],
  routes: {
    root: rootRouteRef,
  },
});
