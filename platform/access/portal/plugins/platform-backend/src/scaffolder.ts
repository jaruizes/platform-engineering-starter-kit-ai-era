import { coreServices, createBackendModule } from '@backstage/backend-plugin-api';
import {
  createTemplateAction,
  scaffolderActionsExtensionPoint,
} from '@backstage/plugin-scaffolder-node';
import { PlatformApiClient, PlatformApiError, type RequestResult } from './platformApi';

const NAME = /^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$/;

/** The secret the portal's form decorator "platform-identity" fills with the person's token. */
export const TOKEN_SECRET = 'platformToken';

/**
 * Software Templates run on behalf of a signed-in person. The form decorator
 * "platform-identity" (frontend plugin) passes the person's Keycloak access
 * token as a task secret, and the actions call the platform API with it: the
 * platform API decides with the person's own teams and roles. Agents do not
 * use the templates: they act through the platform MCP server.
 */
export async function personToken(ctx: {
  secrets?: Record<string, string>;
  getInitiatorCredentials(): Promise<{ principal: unknown }>;
}): Promise<string> {
  const credentials = await ctx.getInitiatorCredentials();
  const principal = credentials.principal as { type?: string };
  if (principal?.type !== 'user') {
    throw new Error('Golden Path templates run on behalf of a person. AI agents use the platform MCP server.');
  }
  const token = ctx.secrets?.[TOKEN_SECRET];
  if (!token) {
    throw new Error(
      'The platform needs to know who you are: sign in to the portal with the platform identity ' +
        '(Keycloak) and fill in the form again. (The template must declare the form decorator platform-identity.)',
    );
  }
  return token;
}

function friendly(error: unknown, what: string): never {
  if (error instanceof PlatformApiError) {
    throw new Error(`The platform did not ${what}: ${error.message}`);
  }
  throw error;
}

/** People get what they ask for or a reason; only agents' requests wait for an approver. */
function outcome(result: RequestResult, what: string): void {
  if (result.status === 'accepted') return;
  if (result.status === 'pending_approval') {
    throw new Error(`${what} needs approval (${result.approval_id}): ${result.reason ?? ''}`);
  }
  throw new Error(`The platform guardrails stopped this request: ${result.reason ?? result.status}`);
}

export function createEnvironmentAction(api: PlatformApiClient) {
  return createTemplateAction({
    id: 'platform:environment:create',
    description: 'Requests an ephemeral environment through the Environment Golden Path, as the signed-in person.',
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
      const token = await personToken(ctx);
      const { name, purpose, size, ttlHours } = ctx.input;
      // The EntityPicker returns a ref like group:default/checkout.
      const team = ctx.input.team.split('/').pop()!;
      if (!NAME.test(team)) {
        throw new Error(`'${team}' is not a valid team name.`);
      }
      ctx.logger.info(`Requesting a ${size} environment '${name}' for team ${team}`);
      try {
        outcome(await api.requestEnvironment(token, { name, team, purpose, size, ttlHours }), 'The environment');
      } catch (error) {
        friendly(error, 'create the environment');
      }
      ctx.output('entityRef', `resource:default/${name}`);
      ctx.output('namespace', `env-${name}`);
    },
  });
}

export function createServiceAction(api: PlatformApiClient) {
  return createTemplateAction({
    id: 'platform:service:deploy',
    description: 'Deploys a service into an environment through the SpringService Golden Path, as the signed-in person.',
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
      const token = await personToken(ctx);
      // The EntityPicker returns a ref like resource:default/payments-dev.
      const environment = ctx.input.environment.split('/').pop()!;
      const { name, image, replicas } = ctx.input;
      ctx.logger.info(`Deploying ${name} into environment ${environment}`);
      try {
        outcome(await api.deployService(token, environment, { name, image, replicas }), 'The service');
      } catch (error) {
        friendly(error, 'deploy the service');
      }
      ctx.output('entityRef', `component:default/${name}.${environment}`);
      ctx.output('url', `http://${name}.env-${environment}.svc.cluster.local`);
    },
  });
}

export function createCapabilityRequestAction(api: PlatformApiClient) {
  return createTemplateAction({
    id: 'platform:capability:request',
    description: 'Requests a platform capability (for example a database) through its Golden Path, as the signed-in person.',
    schema: {
      input: {
        capability: z => z.string().describe('Capability kind, for example PostgresDatabase'),
        name: z => z.string().regex(NAME).describe('Name of what is requested'),
        environment: z => z.string().optional().describe('Environment (name or entity ref)'),
        parameters: z => z.record(z.any()).default({}).describe('Parameters of the capability'),
      },
      output: {
        entityRef: z => z.string(),
      },
    },
    async handler(ctx) {
      const token = await personToken(ctx);
      const environment = ctx.input.environment?.split('/').pop() || undefined;
      if (environment && !NAME.test(environment)) {
        throw new Error(`'${environment}' is not a valid environment name.`);
      }
      // Empty optional fields mean "use the default".
      const parameters = Object.fromEntries(
        Object.entries(ctx.input.parameters).filter(([, v]) => v !== undefined && v !== ''),
      );
      const { name, capability } = ctx.input;
      ctx.logger.info(`Requesting ${capability} ${name}${environment ? ` in env-${environment}` : ''}`);
      try {
        outcome(await api.requestCapability(token, capability, { name, environment, parameters }), capability);
      } catch (error) {
        friendly(error, `create the ${capability}`);
      }
      ctx.output('entityRef', `resource:default/${environment ? `${name}.${environment}` : name}`);
    },
  });
}

/** Drops what the form leaves empty, so the definition only says what was filled in. */
export function compact(value: unknown): unknown {
  if (Array.isArray(value)) {
    const items = value.map(compact).filter(v => v !== undefined);
    return items.length ? items : undefined;
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value)
      .map(([k, v]) => [k, compact(v)] as const)
      .filter(([, v]) => v !== undefined);
    return entries.length ? Object.fromEntries(entries) : undefined;
  }
  if (value === null || value === '' || (typeof value === 'string' && value.startsWith('${{'))) {
    return undefined;
  }
  return value;
}

/**
 * Creates a repository with a code Golden Path (spring-service, angular-app,
 * api-mcp-adapter). The platform API renders the skeleton and creates the
 * repository; the portal only sends what the person filled in, on their behalf.
 */
export function createGoldenPathAction(api: PlatformApiClient) {
  return createTemplateAction({
    id: 'platform:golden-path:create',
    description: 'Creates a repository with a code Golden Path of the platform, on behalf of the signed-in person.',
    schema: {
      input: {
        goldenPath: z => z.string().describe('Code Golden Path, for example spring-service'),
        parameters: z => z.record(z.any()).default({}).describe('Parameters of the Golden Path'),
      },
      output: {
        repositoryUrl: z => z.string(),
        cloneUrl: z => z.string(),
        entityRef: z => z.string(),
      },
    },
    async handler(ctx) {
      const token = await personToken(ctx);
      // Empty optional fields mean "use the default".
      const parameters = Object.fromEntries(
        Object.entries(ctx.input.parameters).filter(([, v]) => v !== undefined && v !== null && v !== ''),
      );
      ctx.logger.info(`Asking the platform to create ${parameters.name} with the ${ctx.input.goldenPath} Golden Path`);
      try {
        const created = await api.createRepository(token, ctx.input.goldenPath, parameters);
        ctx.output('repositoryUrl', created.repository);
        ctx.output('cloneUrl', created.cloneUrl);
        ctx.output('entityRef', created.catalogEntity);
      } catch (error) {
        if (error instanceof PlatformApiError) {
          throw new Error(`The platform did not create the repository: ${error.message}`);
        }
        throw error;
      }
    },
  });
}

/** Proposes a new platform capability: the platform validates it and opens the pull request. */
export function createCapabilityProposalAction(api: PlatformApiClient) {
  return createTemplateAction({
    id: 'platform:capability:propose',
    description:
      'Proposes a new platform capability definition; the platform opens a pull request for an agent to build.',
    schema: {
      input: {
        definition: z => z.record(z.any()).describe('The CapabilityDefinition, as filled in the form'),
      },
      output: {
        pullRequestUrl: z => z.string(),
        entityRef: z => z.string(),
      },
    },
    async handler(ctx) {
      const token = await personToken(ctx);
      const definition = compact(ctx.input.definition);
      const name = ctx.user?.entity?.spec?.profile?.displayName ?? ctx.user?.ref ?? '';
      try {
        const proposed = await api.proposeCapability(token, definition, String(name));
        ctx.logger.info(`Opened pull request #${proposed.pullRequestNumber}: ${proposed.pullRequestUrl}`);
        ctx.output('pullRequestUrl', proposed.pullRequestUrl);
        ctx.output('entityRef', proposed.entityRef);
      } catch (error) {
        if (error instanceof PlatformApiError) {
          throw new Error(`The platform did not accept the proposal: ${error.message}`);
        }
        throw error;
      }
    },
  });
}

export const scaffolderModulePlatform = createBackendModule({
  pluginId: 'scaffolder',
  moduleId: 'platform-golden-paths',
  register(env) {
    env.registerInit({
      deps: { scaffolder: scaffolderActionsExtensionPoint, config: coreServices.rootConfig },
      async init({ scaffolder, config }) {
        const api = new PlatformApiClient(
          config.getOptionalString('platform.api.url') ?? 'http://platform-api.platform-system.svc:8083',
        );
        scaffolder.addActions(
          createEnvironmentAction(api),
          createServiceAction(api),
          createCapabilityRequestAction(api),
          createGoldenPathAction(api),
          createCapabilityProposalAction(api),
        );
      },
    });
  },
});
