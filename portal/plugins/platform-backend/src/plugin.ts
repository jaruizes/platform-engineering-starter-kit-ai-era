import {
  coreServices,
  createBackendPlugin,
} from '@backstage/backend-plugin-api';
import { actionsRegistryServiceRef } from '@backstage/backend-plugin-api/alpha';
import { catalogServiceRef } from '@backstage/plugin-catalog-node';
import { registerActions } from './actions';
import { ConsoleClient } from './console';
import { PlatformClient } from './kubernetes';
import { createRouter } from './router';

/**
 * The platform plugin: agent approvals and AI-era metrics in the portal, and
 * read-only platform context for AI agents through the MCP actions.
 */
export const platformPlugin = createBackendPlugin({
  pluginId: 'platform',
  register(env) {
    env.registerInit({
      deps: {
        auth: coreServices.auth,
        config: coreServices.rootConfig,
        httpAuth: coreServices.httpAuth,
        httpRouter: coreServices.httpRouter,
        actionsRegistry: actionsRegistryServiceRef,
        catalog: catalogServiceRef,
      },
      async init({ auth, config, httpAuth, httpRouter, actionsRegistry, catalog }) {
        const platformConsole = new ConsoleClient(
          config.getOptionalString('platform.consoleUrl') ??
            'http://platform-console.platform-system.svc:8080',
        );
        const platform = new PlatformClient();

        const displayName = async (ref: string) => {
          const entity = await catalog
            .getEntityByRef(ref, { credentials: await auth.getOwnServiceCredentials() })
            .catch(() => undefined);
          const name = (entity?.spec?.profile as { displayName?: string } | undefined)?.displayName;
          return name ? `${name} (${ref})` : ref;
        };

        registerActions(actionsRegistry, platform, platformConsole);
        httpRouter.use(await createRouter({ httpAuth, platformConsole, displayName }));
      },
    });
  },
});
