import type { RootConfigService } from '@backstage/backend-plugin-api';
import { readFileSync } from 'fs';
import { GitServer } from './git';

/**
 * Where the capabilities live:
 *
 *   platform:
 *     capabilities:
 *       schema: ./capabilities/schema/capability-definition.schema.json
 *       repository: { baseUrl: http://localhost:3000, owner: platform, name: platform-starter-kit }
 *
 * The repository credentials are the Gitea integration's.
 */
export function capabilitySettings(config: RootConfigService) {
  const section = config.getOptionalConfig('platform.capabilities');
  const schemaPath = section?.getOptionalString('schema');
  const schema = schemaPath ? JSON.parse(readFileSync(schemaPath, 'utf8')) : undefined;
  const repo = section?.getOptionalConfig('repository');
  const gitea = config.getOptionalConfigArray('integrations.gitea')?.[0];
  const git =
    repo && gitea
      ? new GitServer({
          baseUrl: repo.getString('baseUrl'),
          owner: repo.getString('owner'),
          repo: repo.getString('name'),
          username: gitea.getOptionalString('username') ?? '',
          password: gitea.getOptionalString('password') ?? '',
        })
      : undefined;
  return { schema, git, appUrl: config.getString('app.baseUrl') };
}
