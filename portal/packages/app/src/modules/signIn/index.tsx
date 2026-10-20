import { SignInPage } from '@backstage/core-components';
import { createFrontendModule } from '@backstage/frontend-plugin-api';
import { SignInPageBlueprint } from '@backstage/plugin-app-react';

// The local demo signs in as a guest, mapped to a sample user in the catalog.
// Replace it with your identity provider (Entra ID, Okta, GitHub...).
export const signInModule = createFrontendModule({
  pluginId: 'app',
  extensions: [
    SignInPageBlueprint.make({
      params: {
        loader: async () => props => <SignInPage {...props} auto providers={['guest']} />,
      },
    }),
  ],
});
