import { coreServices, createBackendModule } from '@backstage/backend-plugin-api';
import {
  createTemplateAction,
  scaffolderActionsExtensionPoint,
} from '@backstage/plugin-scaffolder-node';
import Ajv2020 from 'ajv/dist/2020';
import YAML from 'yaml';
import { summarizeCapability } from './capabilities';
import { GitServer } from './git';
import { PlatformClient, PlatformDenied } from './kubernetes';
import { capabilitySettings } from './settings';

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

export function definitionErrors(schema: Record<string, any>, definition: unknown): string[] {
  const ajv = new Ajv2020({ strict: false, allErrors: true });
  const validate = ajv.compile(schema);
  if (validate(definition)) {
    return [];
  }
  return (validate.errors ?? []).map(e => `${e.instancePath || '(root)'} ${e.message}`);
}

export function pullRequestBody(definition: any, requestedBy: string): string {
  const { metadata, spec } = definition;
  const rules = [...spec.guardrails.everyone, ...spec.guardrails.agents];
  return [
    `**${metadata.title}** (\`${spec.interface.kind}\`), proposed by ${requestedBy} from the developer portal.`,
    '',
    `> ${spec.purpose.problem}`,
    '',
    `- ${spec.interface.parameters.length} parameters: ${spec.interface.parameters.map((p: any) => `\`${p.name}\``).join(', ') || 'none'}`,
    `- ${rules.length} guardrails: ${rules.map((r: any) => `${r.id} (${r.enforcement})`).join(', ')}`,
    `- ${spec.acceptance.length} acceptance criteria: ${spec.acceptance.map((a: any) => a.id).join(', ')}`,
    '',
    '## Next steps',
    '',
    '1. **An agent builds it** on this branch with the `build-platform-capability` skill in `agents/skills/`, using Claude Code, Codex or Gemini CLI:',
    `   _"Build the capability in this pull request"_. It never changes \`capability.yaml\`; if something is unclear it asks here.`,
    '2. **CI checks it** against this definition (`platform/capabilities/tools/check.sh`) and writes `TRACEABILITY.md`.',
    '3. **A person on the platform team validates it** and merges. It becomes available as experimental.',
  ].join('\n');
}

export function createCapabilityProposalAction(
  platform: PlatformClient,
  schema?: Record<string, any>,
  git?: GitServer,
) {
  return createTemplateAction({
    id: 'platform:capability:propose',
    description:
      'Opens a pull request in the platform repository with a new capability definition, for an agent to build.',
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
      if (!schema || !git) {
        throw new Error('The portal has no platform repository configured (platform.capabilities).');
      }
      const definition = compact(ctx.input.definition) as any;
      const errors = definitionErrors(schema, definition);
      if (errors.length) {
        throw new Error(`The definition is not valid:\n- ${errors.join('\n- ')}`);
      }
      const name = definition.metadata.name;
      const content =
        '# Written by a platform engineer with the "New platform capability" template.\n' +
        '# An agent builds the capability from it (build-platform-capability skill);\n' +
        '# a person on the platform team validates the result. Agents never edit it.\n' +
        YAML.stringify(definition, { lineWidth: 100 });
      const email = ctx.user?.entity?.spec?.profile
        ? ((ctx.user.entity.spec.profile as { email?: string }).email ?? 'portal@starterkit.local')
        : 'portal@starterkit.local';
      const pr = await git.propose({
        name,
        content,
        title: `New platform capability: ${definition.metadata.title}`,
        body: pullRequestBody(definition, person.name),
        author: { name: person.name, email },
      });
      ctx.logger.info(`Opened pull request #${pr.number}: ${pr.url}`);
      await platform.record(
        'CapabilityProposed',
        `${person.name} proposed the capability ${name} (pull request #${pr.number})`,
        name,
        person.ref,
        'CapabilityDefinition',
      );
      ctx.output('pullRequestUrl', pr.url);
      ctx.output('entityRef', `resource:default/${name}.pr-${pr.number}`);
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
        const { schema, git } = capabilitySettings(config);
        scaffolder.addActions(
          createEnvironmentAction(platform),
          createServiceAction(platform),
          createCapabilityRequestAction(platform),
          createCapabilityProposalAction(platform, schema, git),
        );
      },
    });
  },
});
