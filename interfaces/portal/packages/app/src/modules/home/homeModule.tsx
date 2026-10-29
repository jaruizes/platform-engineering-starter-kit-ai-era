import { createFrontendModule } from '@backstage/frontend-plugin-api';
import { HomePageWidgetBlueprint } from '@backstage/plugin-home-react/alpha';
import { MarkdownContent } from '@backstage/core-components';
import { Typography } from '@material-ui/core';
import { useBrandingText, usePortalTitle } from '../../branding';

// The texts of the welcome card come from app.branding.home (see
// branding/branding.yaml); these are used when it has none.
const defaultSubtitle = 'What this portal offers to people and to AI agents';
const defaultContent = `
The same Golden Paths for developers and AI agents, inside the same guardrails.
`;

const Welcome = () => {
  const title = useBrandingText('home.title', usePortalTitle());
  const subtitle = useBrandingText('home.subtitle', defaultSubtitle);
  const content = useBrandingText('home.content', defaultContent);
  return (
    <>
      <Typography variant="h5">{title}</Typography>
      <Typography variant="body2" color="textSecondary" paragraph>
        {subtitle}
      </Typography>
      <MarkdownContent content={content} />
    </>
  );
};

const gettingStartedWidget = HomePageWidgetBlueprint.make({
  name: 'getting-started',
  params: {
    name: 'GettingStarted',
    description: 'Welcome card, with the texts of the branding',
    components: async () => ({ Content: Welcome }),
  },
});

export const homeModule = createFrontendModule({
  pluginId: 'home',
  extensions: [gettingStartedWidget],
});
