import type {
  CoreV1Api,
  CustomObjectsApi,
  KubeConfig,
} from '@kubernetes/client-node';

/**
 * Read-only access to the Crossplane composite resources behind the Golden
 * Paths, for the catalog and the agents' context. The portal never creates or
 * changes them: every request goes through the platform API with the signed-in
 * person's token (platformApi.ts).
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

export type SpringServiceSummary = {
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

  async listSpringServices(): Promise<KubeObject[]> {
    const { custom } = await this.api();
    const res = await custom.listCustomObjectForAllNamespaces({
      group: GROUP,
      version: VERSION,
      plural: 'springservices',
    });
    return (res as { items: KubeObject[] }).items;
  }

  /** The XRDs of the capabilities built from a CapabilityDefinition. */
  async listCapabilityXrds(): Promise<KubeObject[]> {
    const { custom } = await this.api();
    const res = await custom.listClusterCustomObject({
      group: 'apiextensions.crossplane.io',
      version: 'v2',
      plural: 'compositeresourcedefinitions',
      labelSelector: `${PREFIX}/capability`,
    });
    return (res as { items: KubeObject[] }).items;
  }

  /** What has been requested from a capability, in every environment. */
  async listRequests(capability: { group: string; version: string; plural: string }): Promise<KubeObject[]> {
    const { custom } = await this.api();
    const res = await custom.listCustomObjectForAllNamespaces({
      group: capability.group,
      version: capability.version,
      plural: capability.plural,
    });
    return (res as { items: KubeObject[] }).items;
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

export function summarizeSpringService(service: KubeObject): SpringServiceSummary {
  const annotations = service.metadata.annotations ?? {};
  const namespace = service.metadata.namespace ?? '';
  return {
    name: service.metadata.name,
    namespace,
    environment: namespace.replace(/^env-/, ''),
    image: service.spec?.image,
    replicas: service.spec?.replicas,
    ready: isReady(service),
    url: service.status?.url,
    requestedBy: annotations[`${PREFIX}/requested-by`],
    requesterType: annotations[`${PREFIX}/requester-type`],
  };
}
