import { OAuth2 } from '@backstage/core-app-api';
import {
  ApiBlueprint,
  configApiRef,
  createApiRef,
  discoveryApiRef,
  oauthRequestApiRef,
  type BackstageIdentityApi,
  type OAuthApi,
  type OpenIdConnectApi,
  type ProfileInfoApi,
  type SessionApi,
} from '@backstage/frontend-plugin-api';
import { createScaffolderFormDecorator, FormDecoratorBlueprint } from '@backstage/plugin-scaffolder-react/alpha';

/**
 * The platform identity: people sign in to the portal with Keycloak (the
 * backend's "oidc" provider), and the portal uses the same session to get the
 * person's access token for the platform API. Templates and the AI Platform
 * page send that token, so the platform API decides with the person's own
 * teams and roles, as it does for the CLI and for agents.
 */
export const platformIdentityApiRef = createApiRef<
  OAuthApi & OpenIdConnectApi & ProfileInfoApi & BackstageIdentityApi & SessionApi
>({ id: 'plugin.platform.identity' });

export const platformIdentityApi = ApiBlueprint.make({
  name: 'identity',
  params: defineParams =>
    defineParams({
      api: platformIdentityApiRef,
      deps: {
        discoveryApi: discoveryApiRef,
        oauthRequestApi: oauthRequestApiRef,
        configApi: configApiRef,
      },
      factory: ({ discoveryApi, oauthRequestApi, configApi }) =>
        OAuth2.create({
          configApi,
          discoveryApi,
          oauthRequestApi,
          provider: { id: 'oidc', title: 'Platform identity', icon: () => null },
          environment: configApi.getOptionalString('auth.environment'),
          defaultScopes: ['openid', 'profile', 'email'],
        }),
    }),
});

/** The secret the scaffolder actions read the person's token from (platform-backend/src/scaffolder.ts). */
export const TOKEN_SECRET = 'platformToken';

/**
 * Templates that declare `formDecorators: [{ id: platform-identity }]` send
 * the person's access token, fresh at submit time, as a task secret: secrets
 * are not stored with the task's parameters or shown in its log.
 */
export const platformIdentityDecorator = FormDecoratorBlueprint.make({
  name: 'platform-identity',
  params: {
    decorator: createScaffolderFormDecorator({
      id: 'platform-identity',
      deps: { identity: platformIdentityApiRef },
      async decorator({ setSecrets }, { identity }) {
        const token = await identity.getAccessToken();
        setSecrets(secrets => ({ ...secrets, [TOKEN_SECRET]: token }));
      },
    }),
  },
});
