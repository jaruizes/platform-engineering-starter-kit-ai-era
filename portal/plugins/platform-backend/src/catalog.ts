import {
  coreServices,
  createBackendModule,
  LoggerService,
} from '@backstage/backend-plugin-api';
import type { Entity } from '@backstage/catalog-model';
import {
  catalogProcessingExtensionPoint,
  EntityProvider,
  EntityProviderConnection,
} from '@backstage/plugin-catalog-node';
import {
  capabilityEntity,
  capabilityRequestEntity,
  newCapabilityTemplate,
  proposalEntity,
  requestTemplate,
  summarizeCapability,
} from './capabilities';
import { GitServer } from './git';
import {
  KubeObject,
  PlatformClient,
  PREFIX,
  summarizeApp,
  summarizeEnvironment,
} from './kubernetes';
import { capabilitySettings } from './settings';

const LOCATION = 'platform:golden-paths';

/**
 * Brings what was created through the Golden Paths into the catalog, by
 * humans or by agents: environments as Resources and services as Components,
 * with who asked for them, who approved them and what they cost.
 */
export class PlatformEntityProvider implements EntityProvider {
  private connection?: EntityProviderConnection;

  constructor(
    private readonly platform: PlatformClient,
    private readonly logger: LoggerService,
  ) {}

  getProviderName() {
    return 'platform-golden-paths';
  }

  async connect(connection: EntityProviderConnection) {
    this.connection = connection;
  }

  async refresh() {
    if (!this.connection) {
      return;
    }
    let environments: KubeObject[];
    let apps: KubeObject[];
    try {
      [environments, apps] = await Promise.all([
        this.platform.listEnvironments(),
        this.platform.listApps(),
      ]);
    } catch (error) {
      this.logger.warn(`Could not read the Golden Paths from the cluster: ${error}`);
      return;
    }
    const teams = new Map(environments.map(e => [e.metadata.name, e.spec?.team]));
    const entities = [
      ...environments.map(environmentEntity),
      ...apps.map(app => appEntity(app, teams)),
    ];
    await this.connection.applyMutation({
      type: 'full',
      entities: entities.map(entity => ({ entity, locationKey: LOCATION })),
    });
  }
}

/**
 * Brings the platform capabilities into the catalog: each installed one with
 * a form to request it, what has been requested from it, the definitions
 * waiting in pull requests, and the form to propose a new one. All of it is
 * read from the cluster and the platform repository, so a new capability needs
 * no change in the portal.
 */
export class CapabilitiesEntityProvider implements EntityProvider {
  private connection?: EntityProviderConnection;

  constructor(
    private readonly platform: PlatformClient,
    private readonly settings: { schema?: Record<string, any>; git?: GitServer; appUrl: string },
    private readonly logger: LoggerService,
  ) {}

  getProviderName() {
    return 'platform-capabilities';
  }

  async connect(connection: EntityProviderConnection) {
    this.connection = connection;
  }

  async refresh() {
    if (!this.connection) {
      return;
    }
    const entities: Entity[] = [];
    if (this.settings.schema) {
      entities.push(newCapabilityTemplate(this.settings.schema));
    }
    try {
      const [xrds, environments] = await Promise.all([
        this.platform.listCapabilityXrds(),
        this.platform.listEnvironments(),
      ]);
      const teams = new Map(environments.map(e => [e.metadata.name, e.spec?.team]));
      for (const cap of xrds.map(summarizeCapability)) {
        entities.push(
          capabilityEntity(cap, this.settings.appUrl, this.settings.git?.repositoryUrl),
          requestTemplate(cap, this.settings.appUrl),
        );
        const requests = await this.platform.listRequests(cap).catch(() => []);
        entities.push(...requests.map(r => capabilityRequestEntity(cap, r, teams)));
      }
    } catch (error) {
      this.logger.warn(`Could not read the capabilities from the cluster: ${error}`);
      return;
    }
    if (this.settings.git) {
      try {
        const proposals = await this.settings.git.proposals();
        entities.push(...proposals.map(p => proposalEntity(p.definition, p.pr)));
      } catch (error) {
        this.logger.warn(`Could not read the proposed capabilities from the platform repository: ${error}`);
      }
    }
    await this.connection.applyMutation({
      type: 'full',
      entities: entities.map(entity => ({ entity, locationKey: 'platform:capabilities' })),
    });
  }
}

function base(name: string): Entity['metadata']['annotations'] {
  return {
    'backstage.io/managed-by-location': `${LOCATION}/${name}`,
    'backstage.io/managed-by-origin-location': `${LOCATION}/${name}`,
  };
}

function platformAnnotations(obj: KubeObject): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(obj.metadata.annotations ?? {})) {
    if (key.startsWith(`${PREFIX}/`)) {
      out[key] = value;
    }
  }
  return out;
}

function requesterTag(type?: string): string[] {
  return type ? [`requested-by-${type}`] : [];
}

export function environmentEntity(env: KubeObject): Entity {
  const s = summarizeEnvironment(env);
  const approved = s.approvedBy ? `, approved by ${s.approvedBy}` : '';
  return {
    apiVersion: 'backstage.io/v1alpha1',
    kind: 'Resource',
    metadata: {
      name: s.name,
      title: s.name,
      description:
        `${s.purpose}. Requested by ${s.requesterType ?? 'unknown'} ${s.requestedBy ?? ''}${approved}. ` +
        `${s.size}, ${s.estimatedDailyCostEur.toFixed(2)} EUR/day, expires ${s.expiresAt}.`,
      annotations: {
        ...base(s.name),
        ...platformAnnotations(env),
        [`${PREFIX}/size`]: String(s.size),
        [`${PREFIX}/estimated-daily-cost-eur`]: s.estimatedDailyCostEur.toFixed(2),
        [`${PREFIX}/expires-at`]: s.expiresAt,
        [`${PREFIX}/status`]: s.ready ? 'Ready' : 'Creating',
        'backstage.io/kubernetes-id': s.name,
        'backstage.io/kubernetes-namespace': s.namespace,
        'backstage.io/kubernetes-label-selector': 'app.kubernetes.io/managed-by=platform',
      },
      tags: [...requesterTag(s.requesterType), `size-${s.size}`],
    },
    spec: {
      type: 'environment',
      owner: `group:default/${s.team}`,
      system: 'ephemeral-environments',
      lifecycle: 'ephemeral',
    },
  };
}

export function appEntity(app: KubeObject, teams: Map<string, string | undefined>): Entity {
  const s = summarizeApp(app);
  const team = teams.get(s.environment);
  return {
    apiVersion: 'backstage.io/v1alpha1',
    kind: 'Component',
    metadata: {
      // Services are unique per environment, so the entity name carries both.
      name: `${s.name}.${s.environment}`,
      title: `${s.name} (${s.environment})`,
      description:
        `Deployed through the new-service Golden Path by ${s.requesterType ?? 'unknown'} ` +
        `${s.requestedBy ?? ''}. Internal URL: ${s.url ?? 'pending'}.`,
      annotations: {
        ...base(`${s.environment}/${s.name}`),
        ...platformAnnotations(app),
        [`${PREFIX}/status`]: s.ready ? 'Running' : 'Starting',
        'backstage.io/kubernetes-id': s.name,
        'backstage.io/kubernetes-namespace': s.namespace,
        'backstage.io/kubernetes-label-selector': `app.kubernetes.io/name=${s.name}`,
      },
      tags: requesterTag(s.requesterType),
      links: s.url ? [{ url: s.url, title: 'Internal URL' }] : [],
    },
    spec: {
      type: 'service',
      lifecycle: 'ephemeral',
      owner: team ? `group:default/${team}` : 'group:default/platform-team',
      system: 'ephemeral-environments',
      dependsOn: [`resource:default/${s.environment}`],
    },
  };
}

export const catalogModulePlatform = createBackendModule({
  pluginId: 'catalog',
  moduleId: 'platform-golden-paths',
  register(env) {
    env.registerInit({
      deps: {
        catalog: catalogProcessingExtensionPoint,
        scheduler: coreServices.scheduler,
        logger: coreServices.logger,
        config: coreServices.rootConfig,
      },
      async init({ catalog, scheduler, logger, config }) {
        const platform = new PlatformClient();
        const provider = new PlatformEntityProvider(platform, logger);
        const capabilities = new CapabilitiesEntityProvider(platform, capabilitySettings(config), logger);
        catalog.addEntityProvider(provider, capabilities);
        await scheduler.scheduleTask({
          id: 'platform-golden-paths-refresh',
          frequency: { seconds: 10 },
          timeout: { seconds: 30 },
          initialDelay: { seconds: 5 },
          fn: () => provider.refresh(),
        });
        await scheduler.scheduleTask({
          id: 'platform-capabilities-refresh',
          frequency: { seconds: 15 },
          timeout: { seconds: 60 },
          initialDelay: { seconds: 5 },
          fn: () => capabilities.refresh(),
        });
      },
    });
  },
});
