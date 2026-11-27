import { SignInPage } from '@backstage/core-components';
import { SignInPageProps } from '@backstage/core-plugin-api';
import { createFrontendModule } from '@backstage/frontend-plugin-api';
import { SignInPageBlueprint } from '@backstage/plugin-app-react';
import { platformIdentityApiRef } from '@internal/backstage-plugin-platform';
import { useBrandingText, usePortalTitle } from '../../branding';

// People sign in with the platform identity provider (Keycloak, realm
// "platform"), which can broker your corporate one (Entra ID, Okta...). The
// same session gives the portal the person's token for the platform API.
// Its title comes from app.branding.signIn.title (see branding/branding.yaml).
const BrandedSignInPage = (props: SignInPageProps) => {
  const title = useBrandingText('signIn.title', usePortalTitle());
  return (
    <SignInPage
      {...props}
      title={title}
      align="center"
      providers={[
        {
          id: 'oidc',
          title: 'Platform account',
          message: 'Sign in with your platform account (Keycloak). Demo people are in examples/scenarios/example/demo/users-and-teams.md.',
          apiRef: platformIdentityApiRef,
        },
      ]}
    />
  );
};

export const signInModule = createFrontendModule({
  pluginId: 'app',
  extensions: [
    SignInPageBlueprint.make({
      params: {
        loader: async () => BrandedSignInPage,
      },
    }),
  ],
});
