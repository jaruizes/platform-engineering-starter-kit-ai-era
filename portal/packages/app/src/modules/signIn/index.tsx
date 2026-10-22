import { SignInPage } from '@backstage/core-components';
import { SignInPageProps } from '@backstage/core-plugin-api';
import { createFrontendModule } from '@backstage/frontend-plugin-api';
import { SignInPageBlueprint } from '@backstage/plugin-app-react';
import { useBrandingText, usePortalTitle } from '../../branding';

// The local demo signs in as a guest, mapped to a sample user in the catalog.
// Replace it with your identity provider (Entra ID, Okta, GitHub...).
// Its title comes from app.branding.signIn.title (see branding/branding.yaml).
const BrandedSignInPage = (props: SignInPageProps) => {
  const title = useBrandingText('signIn.title', usePortalTitle());
  return <SignInPage {...props} auto title={title} providers={['guest']} />;
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
