import { createBackendModule } from '@backstage/backend-plugin-api';
import {
  createTemplateAction,
  scaffolderActionsExtensionPoint,
} from '@backstage/plugin-scaffolder-node';
import { PlatformClient, PlatformDenied } from './kubernetes';

const NAME = /^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$/;

/**
 * Software Templates run on behalf of a signed-in person. Agents do not use
 * them: they act through the platform MCP server, with their own identity,
 * so the agent guardrails always apply to them.
 */
async function requester(ctx: {
  user?: { ref?: string; entity?: { spec?: { profile?: { displayName?: string } } } };
  getInitiatorCredentials(): Promise<{ principal: unknown }>;
}): Promise<{ ref: string; name: string }> {
  const credentials = await ctx.getInitiatorCredentials();
  const principal = credentials.principal as { type?: string; userEntityRef?: string };
  const ref = principal?.type === 'user' ? principal.userEntityRef : undefined;
  if (!ref) {
    throw new Error(
      'Golden Path templates run on behalf of a person. AI agents use the platform MCP server.',
    );
  }
  return { ref, name: ctx.user?.entity?.spec?.profile?.displayName ?? ref };
}

function friendly(error: unknown): never {
  if (error instanceof PlatformDenied) {
    throw new Error(`The platform guardrails stopped this request: ${error.message}`);
  }
  throw error;
}

export function createEnvironmentAction(platform: PlatformClient) {
  return createTemplateAction({
    id: 'platform:environment:create',
    description: 'Requests an ephemeral environment through the Environment Golden Path.',
    schema: {
      input: {
        name: z => z.string().regex(NAME).describe('Environment name'),
        team: z => z.string().describe('Team that owns and pays for it (name or group ref)'),
        purpose: z => z.string().min(3).describe('What it is for'),
        size: z => z.enum(['small', 'medium', 'large']).default('small'),
        ttlHours: z => z.number().int().min(1).default(8).describe('Hours until it is deleted'),
      },
      output: {
        entityRef: z => z.string(),
        namespace: z => z.string(),
      },
    },
    async handler(ctx) {
      const person = await requester(ctx);
      const onBehalfOf = person.ref;
      const { name, purpose, size, ttlHours } = ctx.input;
      // The EntityPicker returns a ref like group:default/checkout.
      const team = ctx.input.team.split('/').pop()!;
      if (!NAME.test(team)) {
        throw new Error(`'${team}' is not a valid team name.`);
      }
      ctx.logger.info(`Requesting a ${size} environment '${name}' for team ${team}`);
      try {
        await platform.createEnvironment({ name, team, purpose, size, ttlHours, onBehalfOf });
      } catch (error) {
        friendly(error);
      }
      await platform.record(
        'RequestAccepted',
        `${person.name} got a ${size} environment for team ${team} from the portal: ${purpose}`,
        name,
        onBehalfOf,
      );
      ctx.output('entityRef', `resource:default/${name}`);
      ctx.output('namespace', `env-${name}`);
    },
  });
}

export function createServiceAction(platform: PlatformClient) {
  return createTemplateAction({
    id: 'platform:service:deploy',
    description: 'Deploys a service into an environment through the new-service Golden Path.',
    schema: {
      input: {
        environment: z => z.string().describe('Environment to deploy into (name or entity ref)'),
        name: z => z.string().regex(NAME).describe('Service name'),
        image: z => z.string().optional().describe('Container image'),
        replicas: z => z.number().int().min(1).max(3).default(1),
      },
      output: {
        entityRef: z => z.string(),
        url: z => z.string(),
      },
    },
    async handler(ctx) {
      const person = await requester(ctx);
      const onBehalfOf = person.ref;
      // The EntityPicker returns a ref like resource:default/payments-dev.
      const environment = ctx.input.environment.split('/').pop()!;
      const { name, image, replicas } = ctx.input;
      ctx.logger.info(`Deploying ${name} into environment ${environment}`);
      try {
        await platform.createApp({ environment, name, image, replicas, onBehalfOf });
      } catch (error) {
        friendly(error);
      }
      await platform.record(
        'RequestAccepted',
        `${person.name} deployed ${name} in env-${environment} from the portal`,
        environment,
        onBehalfOf,
      );
      ctx.output('entityRef', `component:default/${name}.${environment}`);
      ctx.output('url', `http://${name}.env-${environment}.svc.cluster.local`);
    },
  });
}

export const scaffolderModulePlatform = createBackendModule({
  pluginId: 'scaffolder',
  moduleId: 'platform-golden-paths',
  register(env) {
    env.registerInit({
      deps: { scaffolder: scaffolderActionsExtensionPoint },
      async init({ scaffolder }) {
        const platform = new PlatformClient();
        scaffolder.addActions(createEnvironmentAction(platform), createServiceAction(platform));
      },
    });
  },
});
