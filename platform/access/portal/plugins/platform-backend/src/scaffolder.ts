import { coreServices, createBackendModule } from '@backstage/backend-plugin-api';
import {
  createTemplateAction,
  scaffolderActionsExtensionPoint,
} from '@backstage/plugin-scaffolder-node';
import { summarizeCapability } from './capabilities';
import { PlatformClient, PlatformDenied } from './kubernetes';
import { PlatformApiClient, PlatformApiError, type Person } from './platformApi';

const NAME = /^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$/;

/**
 * Software Templates run on behalf of a signed-in person. Agents do not use
 * them: they act through the platform MCP server, with their own identity,
 * so the agent guardrails always apply to them.
 */
async function requester(ctx: {
  user?: {
    ref?: string;
    entity?: { spec?: { profile?: { displayName?: string }; memberOf?: string[] } };
  };
  getInitiatorCredentials(): Promise<{ principal: unknown }>;
}): Promise<Person> {
  const credentials = await ctx.getInitiatorCredentials();
  const principal = credentials.principal as { type?: string; userEntityRef?: string };
  const ref = principal?.type === 'user' ? principal.userEntityRef : undefined;
  if (!ref) {
    throw new Error(
      'Golden Path templates run on behalf of a person. AI agents use the platform MCP server.',
    );
  }
  // Until the portal signs people in with Keycloak (increment B), their
  // teams come from the catalog; the platform API authorizes with them.
  const teams = (ctx.user?.entity?.spec?.memberOf ?? []).map(team => team.split('/').pop() ?? team);
  return { ref, name: ctx.user?.entity?.spec?.profile?.displayName ?? ref, teams };
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
    description: 'Deploys a service into an environment through the SpringService Golden Path.',
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
        await platform.createSpringService({ environment, name, image, replicas, onBehalfOf });
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

export function createCapabilityRequestAction(platform: PlatformClient) {
  return createTemplateAction({
    id: 'platform:capability:request',
    description: 'Requests a platform capability (for example a database) through its Golden Path.',
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
      const person = await requester(ctx);
      const xrds = await platform.listCapabilityXrds();
      const capability = xrds.map(summarizeCapability).find(c => c.kind === ctx.input.capability);
      if (!capability) {
        throw new Error(`The platform does not offer ${ctx.input.capability}.`);
      }
      const environment = ctx.input.environment?.split('/').pop();
      if (capability.scope === 'Namespaced' && !(environment && NAME.test(environment))) {
        throw new Error(`${capability.title} lives in an environment: choose one.`);
      }
      // Empty optional fields mean "use the default".
      const parameters = Object.fromEntries(
        Object.entries(ctx.input.parameters).filter(([, v]) => v !== undefined && v !== ''),
      );
      const { name } = ctx.input;
      ctx.logger.info(`Requesting ${capability.kind} ${name}${environment ? ` in env-${environment}` : ''}`);
      try {
        await platform.createCapabilityRequest({ capability, name, environment, parameters, onBehalfOf: person.ref });
      } catch (error) {
        friendly(error);
      }
      await platform.record(
        'RequestAccepted',
        `${person.name} requested ${capability.kind} ${name}${environment ? ` in env-${environment}` : ''} from the portal`,
        name,
        person.ref,
        capability.kind,
      );
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
      const person = await requester(ctx);
      // Empty optional fields mean "use the default".
      const parameters = Object.fromEntries(
        Object.entries(ctx.input.parameters).filter(([, v]) => v !== undefined && v !== null && v !== ''),
      );
      ctx.logger.info(`Asking the platform to create ${parameters.name} with the ${ctx.input.goldenPath} Golden Path`);
      try {
        const created = await api.createRepository(ctx.input.goldenPath, parameters, person);
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
      const person = await requester(ctx);
      const definition = compact(ctx.input.definition);
      try {
        const proposed = await api.proposeCapability(definition, person);
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
        const platform = new PlatformClient();
        const api = new PlatformApiClient(
          config.getOptionalString('platform.api.url') ?? 'http://platform-api.platform-system.svc:8083',
          config.getOptionalString('platform.api.token'),
        );
        scaffolder.addActions(
          createEnvironmentAction(platform),
          createServiceAction(platform),
          createCapabilityRequestAction(platform),
          createGoldenPathAction(api),
          createCapabilityProposalAction(api),
        );
      },
    });
  },
});
