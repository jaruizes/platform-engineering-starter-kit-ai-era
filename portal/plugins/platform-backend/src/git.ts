import YAML from 'yaml';

/**
 * The platform repository in the local Git server (Gitea). Capability
 * definitions live there: the portal opens a pull request for each new one,
 * and shows the open ones in the catalog as proposed.
 */
export type GitServerConfig = {
  baseUrl: string;
  owner: string;
  repo: string;
  username: string;
  password: string;
};

export type PullRequest = { number: number; url: string; title: string; author: string; sha: string };

export const DEFINITION_PATH = /^capabilities\/([a-z0-9-]+)\/capability\.yaml$/;

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
        // The portal opens them with its own account, on behalf of the person in the body.
        author: pull.body?.match(/proposed by (.+?) from the developer portal/)?.[1] ?? pull.user?.login ?? 'unknown',
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

  /** Opens a pull request that adds or changes capabilities/<name>/capability.yaml. */
  async propose(options: {
    name: string;
    content: string;
    title: string;
    body: string;
    author: { name: string; email: string };
  }): Promise<PullRequest> {
    const path = `capabilities/${options.name}/capability.yaml`;
    const branch = `capability/${options.name}-${Date.now().toString(36)}`;
    const existing = await this.api(`/contents/${path}?ref=main`);
    const sha = existing.ok ? ((await existing.json()) as { sha: string }).sha : undefined;
    await this.json(`/contents/${path}`, {
      method: sha ? 'PUT' : 'POST',
      body: JSON.stringify({
        content: Buffer.from(options.content).toString('base64'),
        message: options.title,
        branch: 'main',
        new_branch: branch,
        author: options.author,
        committer: options.author,
        ...(sha ? { sha } : {}),
      }),
    });
    const pull = await this.json<any>('/pulls', {
      method: 'POST',
      body: JSON.stringify({ head: branch, base: 'main', title: options.title, body: options.body }),
    });
    return { number: pull.number, url: pull.html_url, title: pull.title, author: options.author.name, sha: pull.head?.sha };
  }
}
