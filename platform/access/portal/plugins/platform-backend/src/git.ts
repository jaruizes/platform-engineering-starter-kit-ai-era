import YAML from 'yaml';

/**
 * The platform repository in the local Git server (Gitea). Capability
 * definitions live there: the platform API opens a pull request for each new
 * one (from any channel), and the portal shows the open ones in the catalog
 * as proposed. The portal only reads them.
 */
export type GitServerConfig = {
  baseUrl: string;
  owner: string;
  repo: string;
  username: string;
  password: string;
};

export type PullRequest = { number: number; url: string; title: string; author: string; sha: string };

export const DEFINITION_PATH = /^platform\/capabilities\/infrastructure\/([a-z0-9-]+)\/capability\.yaml$/;

export class GitServer {
  constructor(private readonly config: GitServerConfig) {}

  get repositoryUrl() {
    return `${this.config.baseUrl}/${this.config.owner}/${this.config.repo}`;
  }

  private async api(path: string, init?: RequestInit): Promise<Response> {
    const auth = Buffer.from(`${this.config.username}:${this.config.password}`).toString('base64');
    const response = await fetch(
      `${this.config.baseUrl}/api/v1/repos/${this.config.owner}/${this.config.repo}${path}`,
      {
        ...init,
        headers: { Authorization: `Basic ${auth}`, 'Content-Type': 'application/json', ...init?.headers },
      },
    );
    return response;
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await this.api(path, init);
    if (!response.ok) {
      throw new Error(`Git server: ${init?.method ?? 'GET'} ${path} answered ${response.status}: ${await response.text()}`);
    }
    return (await response.json()) as T;
  }

  /** Capability definitions added or changed by open pull requests. */
  async proposals(): Promise<Array<{ definition: any; pr: PullRequest }>> {
    const pulls = await this.json<any[]>('/pulls?state=open&limit=50');
    const found = [];
    for (const pull of pulls) {
      const pr: PullRequest = {
        number: pull.number,
        url: pull.html_url,
        title: pull.title,
        // The platform opens them with its own account, on behalf of the person in the body.
        author:
          pull.body?.match(/proposed by (.+?) (?:through the platform|from the developer portal)/)?.[1] ??
          pull.user?.login ??
          'unknown',
        sha: pull.head?.sha,
      };
      const files = await this.json<Array<{ filename: string; status: string }>>(`/pulls/${pull.number}/files`);
      for (const file of files.filter(f => DEFINITION_PATH.test(f.filename) && f.status !== 'removed')) {
        const raw = await this.api(`/raw/${file.filename}?ref=${pr.sha}`);
        if (raw.ok) {
          found.push({ definition: YAML.parse(await raw.text()), pr });
        }
      }
    }
    return found;
  }
}
