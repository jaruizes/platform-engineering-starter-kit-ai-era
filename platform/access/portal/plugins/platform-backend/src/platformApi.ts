/**
 * Client for the platform API (platform/capabilities/api). Code Golden Paths
 * (new repositories) and capability proposals are platform capabilities: the
 * portal is one of their channels, like the platform MCP server and the CLI.
 * It sends what the person filled in, on their behalf, and shows the result.
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

export class PlatformApiError extends Error {}

export class PlatformApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string | undefined,
  ) {}

  private async post<T>(path: string, body: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        },
        body: JSON.stringify(body),
      });
    } catch (error) {
      throw new PlatformApiError(`The platform API is not reachable: ${(error as Error).message}`);
    }
    const data = (await res.json().catch(() => ({}))) as any;
    if (!res.ok) {
      throw new PlatformApiError(data?.error ?? `The platform API answered ${res.status}`);
    }
    return data as T;
  }

  createRepository(goldenPath: string, parameters: Record<string, unknown>, requester: string) {
    return this.post<RepositoryCreated>(
      `/v1/golden-paths/${encodeURIComponent(goldenPath)}/repositories`,
      { parameters, requester },
    );
  }

  proposeCapability(definition: unknown, requester: string, requesterName: string) {
    return this.post<CapabilityProposed>('/v1/capability-proposals', {
      definition,
      requester,
      requesterName,
    });
  }
}
