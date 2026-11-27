import {
  coreServices,
  createBackendPlugin,
} from '@backstage/backend-plugin-api';
import { actionsRegistryServiceRef } from '@backstage/backend-plugin-api/alpha';
import { catalogServiceRef } from '@backstage/plugin-catalog-node';
import { registerActions } from './actions';
import { ConsoleClient } from './console';
import { PlatformClient } from './kubernetes';
import { PlatformApiClient } from './platformApi';
import { createRouter } from './router';
import { registerStandardsActions, StandardsLibrary } from './standards';

/**
 * The platform plugin: agent approvals and AI-era metrics in the portal
 * (from the platform API, with the signed-in person's token), and
 * read-only platform context and engineering standards for AI agents
 * through the MCP actions.
 */
export const platformPlugin = createBackendPlugin({
  pluginId: 'platform',
  register(env) {
    env.registerInit({
      deps: {
        config: coreServices.rootConfig,
        httpAuth: coreServices.httpAuth,
        httpRouter: coreServices.httpRouter,
        actionsRegistry: actionsRegistryServiceRef,
        catalog: catalogServiceRef,
      },
      async init({ config, httpAuth, httpRouter, actionsRegistry, catalog }) {
        const platformConsole = new ConsoleClient(
          config.getOptionalString('platform.consoleUrl') ??
            'http://platform-console.platform-system.svc:8080',
        );
        const platform = new PlatformClient();
        const api = new PlatformApiClient(
          config.getOptionalString('platform.api.url') ?? 'http://platform-api.platform-system.svc:8083',
        );

        registerActions(actionsRegistry, platform, platformConsole);
        registerStandardsActions(
          actionsRegistry,
          new StandardsLibrary(
            config.getOptionalString('platform.standardsDir') ?? './standards',
            `${config.getString('app.baseUrl')}/docs/default/component/engineering-standards`,
          ),
          catalog,
        );
        httpRouter.use(await createRouter({
          httpAuth,
          api,
          qualityGitUrl: config.getOptionalString('platform.quality.gitUrl') ?? 'http://gitea.platform-system.svc:3000',
        }));
      },
    });
  },
});
