/**
 * Client for the platform API (platform/capabilities/api). Every capability
 * of the platform lives there; the portal is one of its channels, like the
 * platform MCP server and the CLI.
 *
 * The portal calls it with the signed-in person's Keycloak access token: the
 * platform API knows who they are and which teams and roles they have, and
 * decides. The portal makes no authorization decision of its own and has no
 * token of its own for the platform API.
 */
export type RepositoryCreated = {
  status: string;
  name: string;
  repository: string;
  cloneUrl: string;
  catalogEntity: string;
  environment?: string | null;
};

export type CapabilityProposed = {
  status: string;
  name: string;
  pullRequestUrl: string;
  pullRequestNumber: number;
  entityRef: string;
};

/** What the platform answers to a request: done, waiting for an approver, or stopped by a guardrail. */
export type RequestResult = {
  status: 'accepted' | 'pending_approval' | 'denied' | 'not_ready' | string;
  reason?: string;
  approval_id?: string;
  next_step?: string;
  [key: string]: unknown;
};

export class PlatformApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export class PlatformApiClient {
  constructor(private readonly baseUrl: string) {}

  async call<T>(method: string, path: string, token: string, body?: unknown): Promise<T> {
    if (!token) {
      throw new PlatformApiError(
        'Sign in to the portal with the platform identity (Keycloak) to use the platform.',
        401,
      );
    }
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (error) {
      throw new PlatformApiError(`The platform API is not reachable: ${(error as Error).message}`, 502);
    }
    const data = (await res.json().catch(() => ({}))) as any;
    if (!res.ok) {
      throw new PlatformApiError(data?.error ?? `The platform API answered ${res.status}`, res.status);
    }
    return data as T;
  }

  createRepository(token: string, goldenPath: string, parameters: Record<string, unknown>) {
    return this.call<RepositoryCreated>(
      'POST',
      `/v1/golden-paths/${encodeURIComponent(goldenPath)}/repositories`,
      token,
      { parameters },
    );
  }

  proposeCapability(token: string, definition: unknown, requesterName: string) {
    return this.call<CapabilityProposed>('POST', '/v1/capability-proposals', token, {
      definition,
      requesterName,
    });
  }

  requestEnvironment(
    token: string,
    request: { team: string; name: string; purpose: string; size: string; ttlHours: number },
  ) {
    return this.call<RequestResult>('POST', '/v1/environments', token, request);
  }

  deployService(
    token: string,
    environment: string,
    request: { name: string; image?: string; replicas: number },
  ) {
    return this.call<RequestResult>(
      'POST',
      `/v1/environments/${encodeURIComponent(environment)}/services`,
      token,
      request,
    );
  }

  requestCapability(
    token: string,
    capability: string,
    request: { name: string; environment?: string; parameters: Record<string, unknown> },
  ) {
    return this.call<RequestResult>(
      'POST',
      `/v1/capabilities/${encodeURIComponent(capability)}/requests`,
      token,
      request,
    );
  }

  /** The AI Platform page: what the platform is doing, for the person's teams. */
  overview(token: string) {
    return this.call<Record<string, unknown>>('GET', '/v1/overview', token);
  }

  /** Approves or rejects an agent's request; the platform checks the approver role and four eyes. */
  decide(token: string, id: string, decision: 'approve' | 'reject', note?: string) {
    return this.call<Record<string, unknown>>(
      'POST',
      `/v1/approvals/${encodeURIComponent(id)}/decision`,
      token,
      { decision, note },
    );
  }
}
