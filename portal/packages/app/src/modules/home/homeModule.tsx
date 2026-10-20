import { createFrontendModule } from '@backstage/frontend-plugin-api';
import { HomePageWidgetBlueprint } from '@backstage/plugin-home-react/alpha';
import { MarkdownContent } from '@backstage/core-components';

const content = `
## Platform Starter Kit

The same Golden Paths for developers and AI agents, inside the same guardrails.

- **Create** an [ephemeral environment](/create/templates/default/ephemeral-environment)
  or deploy a [new service](/create/templates/default/new-service).
- **AI Platform**: approve what agents cannot do alone, and follow the
  AI-era metrics in the [AI Platform](/ai-platform) page.
- **Agents** read context from this portal through MCP and act through the
  platform MCP server. Both are in the [APIs](/api-docs) page.
- **Rules and skills** for agents are in the catalog as AI resources.
`;

const gettingStartedWidget = HomePageWidgetBlueprint.make({
  name: 'getting-started',
  params: {
    name: 'GettingStarted',
    title: 'Platform Starter Kit',
    description: 'What this portal offers to people and to AI agents',
    components: async () => ({
      Content: () => <MarkdownContent content={content} />,
    }),
  },
});

export const homeModule = createFrontendModule({
  pluginId: 'home',
  extensions: [gettingStartedWidget],
});
