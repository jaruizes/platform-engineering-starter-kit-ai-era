import type {
  CoreV1Api,
  CustomObjectsApi,
  KubeConfig,
} from '@kubernetes/client-node';

/**
 * Access to the platform API (the Crossplane composite resources behind the
 * Golden Paths). The portal acts with its own Kubernetes identity, and the
 * Kyverno policies record which Backstage user it acts on behalf of.
 */

export const GROUP = 'platform.starterkit.dev';
export const VERSION = 'v1alpha1';
export const PREFIX = 'platform.starterkit.dev';
export const PLATFORM_NAMESPACE = 'platform-system';

export type KubeObject = {
  apiVersion?: string;
  kind?: string;
  metadata: {
    name: string;
    namespace?: string;
    annotations?: Record<string, string>;
    labels?: Record<string, string>;
    creationTimestamp?: string;
  };
  spec?: Record<string, any>;
  status?: Record<string, any>;
};

export type EnvironmentSummary = {
  name: string;
  team: string;
  size: string;
  purpose: string;
  namespace: string;
  ready: boolean;
  estimatedDailyCostEur: number;
  requestedBy?: string;
  requesterType?: string;
  approvedBy?: string;
  createdAt: string;
  expiresAt: string;
};

export type AppSummary = {
  name: string;
  namespace: string;
  environment: string;
  image?: string;
  replicas?: number;
  ready: boolean;
  url?: string;
  requestedBy?: string;
  requesterType?: string;
};

/** A guardrail (Kyverno policy) or a conflict rejected the request. */
export class PlatformDenied extends Error {}

type Clients = { kc: KubeConfig; custom: CustomObjectsApi; core: CoreV1Api };

export class PlatformClient {
  private clients?: Promise<Clients>;

  private async api(): Promise<Clients> {
    if (!this.clients) {
      this.clients = import('@kubernetes/client-node').then(k8s => {
        const kc = new k8s.KubeConfig();
        kc.loadFromDefault();
        return {
          kc,
          custom: kc.makeApiClient(k8s.CustomObjectsApi),
          core: kc.makeApiClient(k8s.CoreV1Api),
        };
      });
    }
    return this.clients;
  }

  async listEnvironments(): Promise<KubeObject[]> {
    const { custom } = await this.api();
    const res = await custom.listClusterCustomObject({
      group: GROUP,
      version: VERSION,
      plural: 'environments',
    });
    return (res as { items: KubeObject[] }).items;
  }

  async listApps(): Promise<KubeObject[]> {
    const { custom } = await this.api();
    const res = await custom.listCustomObjectForAllNamespaces({
      group: GROUP,
      version: VERSION,
      plural: 'apps',
    });
    return (res as { items: KubeObject[] }).items;
  }

  async createEnvironment(options: {
    name: string;
    team: string;
    purpose: string;
    size: string;
    ttlHours: number;
    onBehalfOf: string;
  }): Promise<void> {
    const { custom } = await this.api();
    const body = {
      apiVersion: `${GROUP}/${VERSION}`,
      kind: 'Environment',
      metadata: {
        name: options.name,
        annotations: {
          [`${PREFIX}/purpose`]: options.purpose,
          [`${PREFIX}/on-behalf-of`]: options.onBehalfOf,
        },
      },
      spec: {
        team: options.team,
        purpose: options.purpose,
        size: options.size,
        ttlHours: options.ttlHours,
      },
    };
    await this.guard(`An environment called '${options.name}' already exists.`, () =>
      custom.createClusterCustomObject({
        group: GROUP,
        version: VERSION,
        plural: 'environments',
        body,
      }),
    );
  }

  async createApp(options: {
    environment: string;
    name: string;
    image?: string;
    replicas: number;
    onBehalfOf: string;
  }): Promise<void> {
    const { custom } = await this.api();
    const namespace = `env-${options.environment}`;
    const spec: Record<string, unknown> = { replicas: options.replicas };
    if (options.image) {
      spec.image = options.image;
    }
    const body = {
      apiVersion: `${GROUP}/${VERSION}`,
      kind: 'App',
      metadata: {
        name: options.name,
        namespace,
        annotations: { [`${PREFIX}/on-behalf-of`]: options.onBehalfOf },
      },
      spec,
    };
    await this.guard(`A service called '${options.name}' already exists in ${namespace}.`, () =>
      custom.createNamespacedCustomObject({
        group: GROUP,
        version: VERSION,
        namespace,
        plural: 'apps',
        body,
      }),
    );
  }

  /** Records the action in the platform audit trail, next to the agents' actions. */
  async record(action: string, message: string, subject: string, actor: string) {
    const { core } = await this.api();
    const now = new Date();
    try {
      await core.createNamespacedEvent({
        namespace: PLATFORM_NAMESPACE,
        body: {
          metadata: {
            generateName: 'platform-',
            namespace: PLATFORM_NAMESPACE,
            annotations: { [`${PREFIX}/actor`]: actor },
          },
          involvedObject: {
            apiVersion: `${GROUP}/${VERSION}`,
            kind: 'Environment',
            name: subject,
            namespace: PLATFORM_NAMESPACE,
          },
          reason: action,
          message,
          type: 'Normal',
          source: { component: 'platform-portal' },
          firstTimestamp: now,
          lastTimestamp: now,
          count: 1,
        },
      });
    } catch {
      // The audit trail must never break the request itself.
    }
  }

  private async guard(conflict: string, call: () => Promise<unknown>) {
    try {
      await call();
    } catch (error: any) {
      const code = error?.code;
      const body = typeof error?.body === 'string' ? error.body : JSON.stringify(error?.body ?? '');
      if (code === 409) {
        throw new PlatformDenied(conflict);
      }
      if ([400, 403, 422].includes(code) && body.includes('admission webhook')) {
        throw new PlatformDenied(denialReason(body));
      }
      throw error;
    }
  }
}

/** Extracts the policy message from an admission rejection. */
export function denialReason(body: string): string {
  let message = body;
  try {
    message = JSON.parse(body).message ?? body;
  } catch {
    // Not JSON, keep the raw text.
  }
  for (const marker of ['failed: ', 'denied the request: ']) {
    if (message.includes(marker)) {
      message = message.split(marker).pop()!;
    }
  }
  return message.trim();
}

function isReady(obj: KubeObject): boolean {
  return (obj.status?.conditions ?? []).some(
    (c: { type?: string; status?: string }) => c.type === 'Ready' && c.status === 'True',
  );
}

export function summarizeEnvironment(env: KubeObject): EnvironmentSummary {
  const annotations = env.metadata.annotations ?? {};
  const created = new Date(env.metadata.creationTimestamp ?? Date.now());
  const ttlHours = Number(env.spec?.ttlHours ?? 8);
  return {
    name: env.metadata.name,
    team: env.spec?.team,
    size: env.spec?.size,
    purpose: env.spec?.purpose,
    namespace: env.status?.namespace ?? `env-${env.metadata.name}`,
    ready: isReady(env),
    estimatedDailyCostEur: Number(env.status?.estimatedDailyCost ?? 0),
    requestedBy: annotations[`${PREFIX}/requested-by`],
    requesterType: annotations[`${PREFIX}/requester-type`],
    approvedBy: annotations[`${PREFIX}/approved-by`],
    createdAt: created.toISOString(),
    expiresAt: new Date(created.getTime() + ttlHours * 3600_000).toISOString(),
  };
}

export function summarizeApp(app: KubeObject): AppSummary {
  const annotations = app.metadata.annotations ?? {};
  const namespace = app.metadata.namespace ?? '';
  return {
    name: app.metadata.name,
    namespace,
    environment: namespace.replace(/^env-/, ''),
    image: app.spec?.image,
    replicas: app.spec?.replicas,
    ready: isReady(app),
    url: app.status?.url,
    requestedBy: annotations[`${PREFIX}/requested-by`],
    requesterType: annotations[`${PREFIX}/requester-type`],
  };
}
