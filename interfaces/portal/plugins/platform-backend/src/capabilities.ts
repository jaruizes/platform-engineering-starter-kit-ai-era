import type { Entity } from '@backstage/catalog-model';
import { KubeObject, PREFIX } from './kubernetes';

/**
 * Platform capabilities built from a CapabilityDefinition (platform/capabilities/<name>/
 * in the platform repository). Their XRD carries everything the portal needs:
 * a label to find them and annotations with the title, guardrails, cost and
 * examples. So a new capability appears in the catalog, with a form to request
 * it, without any code or template of its own in the portal.
 */

export const CAPABILITY_LABEL = `${PREFIX}/capability`;

export type Parameter = {
  type: string;
  description?: string;
  enum?: string[];
  default?: unknown;
  minimum?: number;
  maximum?: number;
};

export type Capability = {
  name: string;
  kind: string;
  plural: string;
  group: string;
  version: string;
  scope: 'Namespaced' | 'Cluster';
  title: string;
  description: string;
  owner: string;
  stage: string;
  parameters: Record<string, Parameter>;
  outputs: { secret?: string[]; status?: string[] };
  guardrails: string[];
  examples: string[];
  cost: Record<string, string>;
};

function json<T>(raw: string | undefined, fallback: T): T {
  try {
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function summarizeCapability(xrd: KubeObject): Capability {
  const spec = xrd.spec as any;
  const annotations = xrd.metadata.annotations ?? {};
  const version = spec.versions[spec.versions.length - 1];
  const props =
    version?.schema?.openAPIV3Schema?.properties?.spec?.properties ?? ({} as Record<string, any>);
  const parameters: Record<string, Parameter> = {};
  for (const [name, prop] of Object.entries<any>(props)) {
    const { type, description, enum: values, default: def, minimum, maximum } = prop;
    parameters[name] = { type, description, enum: values, default: def, minimum, maximum };
  }
  return {
    name: xrd.metadata.labels?.[CAPABILITY_LABEL] ?? xrd.metadata.name,
    kind: spec.names.kind,
    plural: spec.names.plural,
    group: spec.group,
    version: version.name,
    scope: spec.scope ?? 'Namespaced',
    title: annotations[`${PREFIX}/title`] ?? spec.names.kind,
    description: annotations[`${PREFIX}/description`] ?? '',
    owner: annotations[`${PREFIX}/owner`] ?? 'group:default/platform-team',
    stage: annotations[`${PREFIX}/stage`] ?? 'experimental',
    parameters,
    outputs: json(annotations[`${PREFIX}/outputs`], {}),
    guardrails: json(annotations[`${PREFIX}/guardrails`], []),
    examples: json(annotations[`${PREFIX}/examples`], []),
    cost: json(annotations[`${PREFIX}/cost`], {}),
  };
}

const LOCATION = 'platform:capabilities';

function managedBy(key: string): Record<string, string> {
  return {
    'backstage.io/managed-by-location': `${LOCATION}/${key}`,
    'backstage.io/managed-by-origin-location': `${LOCATION}/${key}`,
  };
}

function costText(cost: Record<string, string>): string {
  const entries = Object.entries(cost);
  return entries.length
    ? ` Estimated cost per day: ${entries.map(([size, eur]) => `${size} ${eur} EUR`).join(', ')}.`
    : '';
}

/**
 * The capability itself, as offered by the platform team. Its documentation is
 * built into the portal image from its folder in the platform repository.
 */
export function capabilityEntity(cap: Capability, appUrl: string, repositoryUrl?: string): Entity {
  const source = repositoryUrl && `${repositoryUrl}/src/branch/main/platform/capabilities/${cap.name}`;
  return {
    apiVersion: 'backstage.io/v1alpha1',
    kind: 'Resource',
    metadata: {
      name: cap.name,
      title: cap.title,
      description: `${cap.description}${costText(cap.cost)}`,
      annotations: {
        ...managedBy(cap.name),
        [`${PREFIX}/kind`]: cap.kind,
        [`${PREFIX}/guardrails`]: JSON.stringify(cap.guardrails),
        ...(source
          ? { 'backstage.io/techdocs-ref': `url:${source}`, 'backstage.io/source-location': `url:${source}` }
          : {}),
      },
      tags: ['platform-capability', cap.stage],
      links: [
        { url: `${appUrl}/create/templates/default/request-${cap.name}`, title: `Request a ${cap.title}` },
        ...(source ? [{ url: `${appUrl}/docs/default/resource/${cap.name}`, title: 'Documentation' }] : []),
      ],
    },
    spec: {
      type: 'platform-capability',
      lifecycle: cap.stage,
      owner: cap.owner,
      system: 'internal-developer-platform',
    },
  };
}

/** Something a person or an agent requested from a capability. */
export function capabilityRequestEntity(
  cap: Capability,
  obj: KubeObject,
  teams: Map<string, string | undefined>,
): Entity {
  const annotations = obj.metadata.annotations ?? {};
  const namespace = obj.metadata.namespace;
  const environment = namespace?.replace(/^env-/, '');
  const ready = (obj.status?.conditions ?? []).some(
    (c: { type?: string; status?: string }) => c.type === 'Ready' && c.status === 'True',
  );
  const requester = `${annotations[`${PREFIX}/requester-type`] ?? 'unknown'} ${
    annotations[`${PREFIX}/requested-by`] ?? ''
  }`.trim();
  const approved = annotations[`${PREFIX}/approved-by`]
    ? `, approved by ${annotations[`${PREFIX}/approved-by`]}`
    : '';
  const params = Object.entries(obj.spec ?? {})
    .filter(([k]) => k !== 'crossplane')
    .map(([k, v]) => `${k} ${v}`)
    .join(', ');
  const cost = obj.status?.estimatedDailyCost ? `, ${obj.status.estimatedDailyCost} EUR/day` : '';
  const team = environment ? teams.get(environment) : undefined;
  const key = environment ? `${obj.metadata.name}.${environment}` : obj.metadata.name;
  return {
    apiVersion: 'backstage.io/v1alpha1',
    kind: 'Resource',
    metadata: {
      name: key,
      title: environment ? `${obj.metadata.name} (${environment})` : obj.metadata.name,
      description: `${cap.title} requested by ${requester}${approved}. ${params}${cost}.`,
      annotations: {
        ...managedBy(`${cap.name}/${key}`),
        [`${PREFIX}/status`]: ready ? 'Ready' : 'Creating',
        ...(obj.status?.secretName ? { [`${PREFIX}/secret`]: obj.status.secretName } : {}),
        ...Object.fromEntries(Object.entries(annotations).filter(([k]) => k.startsWith(`${PREFIX}/`))),
      },
      tags: annotations[`${PREFIX}/requester-type`]
        ? [`requested-by-${annotations[`${PREFIX}/requester-type`]}`]
        : [],
    },
    spec: {
      type: cap.name,
      lifecycle: 'ephemeral',
      owner: team ? `group:default/${team}` : cap.owner,
      system: 'ephemeral-environments',
      dependsOn: [
        `resource:default/${cap.name}`,
        ...(environment ? [`resource:default/${environment}`] : []),
      ],
    },
  };
}

/** The form to request a capability, built from its parameters. */
export function requestTemplate(cap: Capability, appUrl: string): Entity {
  const properties: Record<string, any> = {};
  const required = ['name'];
  if (cap.scope === 'Namespaced') {
    required.unshift('environment');
    properties.environment = {
      title: 'Environment',
      type: 'string',
      description: 'Environment it goes into',
      'ui:field': 'EntityPicker',
      'ui:options': { catalogFilter: { kind: 'Resource', 'spec.type': 'environment' } },
    };
  }
  properties.name = {
    title: 'Name',
    type: 'string',
    description: 'Lowercase letters, numbers and dashes',
    pattern: '^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$',
  };
  const parameters: Record<string, string> = {};
  for (const [name, p] of Object.entries(cap.parameters)) {
    properties[name] = {
      title: name.charAt(0).toUpperCase() + name.slice(1),
      type: p.type,
      description:
        name === 'size' && cap.cost[String(p.default ?? '')] !== undefined
          ? `${p.description ?? ''} Cost per day: ${Object.entries(cap.cost)
              .map(([s, eur]) => `${s} ${eur} EUR`)
              .join(', ')}.`
          : p.description,
      ...(p.enum ? { enum: p.enum } : {}),
      ...(p.default !== undefined ? { default: p.default } : {}),
      ...(p.minimum !== undefined ? { minimum: p.minimum } : {}),
      ...(p.maximum !== undefined ? { maximum: p.maximum } : {}),
    };
    if (p.default === undefined) {
      required.push(name);
    }
    parameters[name] = `\${{ parameters.${name} }}`;
  }
  const guardrails = cap.guardrails.map(g => `- ${g}`).join('\n');
  return {
    apiVersion: 'scaffolder.backstage.io/v1beta3',
    kind: 'Template',
    metadata: {
      name: `request-${cap.name}`,
      title: cap.title,
      description: `${cap.description}${costText(cap.cost)}`,
      annotations: managedBy(`request-${cap.name}`),
      tags: ['platform-capability', cap.stage],
    },
    spec: {
      owner: cap.owner,
      type: 'platform-capability',
      parameters: [
        {
          title: `Request a ${cap.title}`,
          description: guardrails ? `Guardrails:\n${guardrails}` : undefined,
          required,
          properties,
        },
      ],
      steps: [
        {
          id: 'request',
          name: `Request the ${cap.title}`,
          action: 'platform:capability:request',
          input: {
            capability: cap.kind,
            name: '${{ parameters.name }}',
            ...(cap.scope === 'Namespaced' ? { environment: '${{ parameters.environment }}' } : {}),
            parameters,
          },
        },
      ],
      output: {
        links: [
          { title: 'Open in the catalog', entityRef: '${{ steps.request.output.entityRef }}' },
          { title: `${cap.title} documentation`, url: `${appUrl}/docs/default/resource/${cap.name}` },
        ],
        text: [
          {
            title: 'What you get',
            content: cap.outputs.secret?.length
              ? `A Secret with ${cap.outputs.secret.join(', ')}. The catalog entry shows its name and says ` +
                'Ready when you can use it.'
              : 'The catalog entry says Ready when you can use it.',
          },
        ],
      },
    },
  };
}

// --- New capabilities ---------------------------------------------------------

type JsonSchema = Record<string, any>;

/** Inlines the local $refs, so each form page is a plain JSON schema. */
function resolve(node: unknown, defs: Record<string, JsonSchema>): any {
  if (Array.isArray(node)) {
    return node.map(n => resolve(n, defs));
  }
  if (node && typeof node === 'object') {
    const obj = node as JsonSchema;
    if (typeof obj.$ref === 'string' && obj.$ref.startsWith('#/$defs/')) {
      return resolve(defs[obj.$ref.slice('#/$defs/'.length)], defs);
    }
    return Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, resolve(v, defs)]));
  }
  return node;
}

/**
 * The "New platform capability" form, built from the CapabilityDefinition
 * schema: one page per section. A field added to the schema appears in the form.
 */
export function newCapabilityTemplate(schema: JsonSchema): Entity {
  const defs = schema.$defs as Record<string, JsonSchema>;
  const spec = schema.properties.spec;
  const metadata = resolve(schema.properties.metadata, defs);
  metadata.properties.owner = {
    ...metadata.properties.owner,
    'ui:field': 'OwnerPicker',
    'ui:options': { catalogFilter: { kind: 'Group' } },
  };
  const page = (title: string, description: string, sections: string[], required: string[]) => ({
    title,
    description,
    required,
    properties: Object.fromEntries(sections.map(s => [s, resolve(spec.properties[s], defs)])),
  });
  const optional = ['implementation', 'lifecycle', 'ownership', 'delivery'];
  return {
    apiVersion: 'scaffolder.backstage.io/v1beta3',
    kind: 'Template',
    metadata: {
      name: 'new-platform-capability',
      title: 'New platform capability',
      description:
        'For the platform team: describe what the platform needs (contract, guardrails and acceptance ' +
        'criteria). It opens a pull request in the platform repository; an agent builds the capability ' +
        'from it and a person on the team validates it.',
      annotations: managedBy('new-platform-capability'),
      tags: ['platform-team', 'ai'],
    },
    spec: {
      owner: 'group:default/platform-team',
      type: 'platform-capability',
      parameters: [
        { title: 'Capability', description: metadata.description, required: ['metadata'], properties: { metadata } },
        page('Purpose', 'Why the platform needs it.', ['purpose'], ['purpose']),
        page('Interface', 'What people and agents can ask for, and what they get.', ['interface'], ['interface']),
        page('Guardrails', 'The limits, for everyone and for agents.', ['guardrails'], ['guardrails']),
        page('Acceptance criteria', 'How we know it works. Each one becomes a test.', ['acceptance'], ['acceptance']),
        page('More (optional)', 'Constraints, lifecycle, ownership and delivery.', optional, []),
      ],
      steps: [
        {
          id: 'propose',
          name: 'Open the pull request',
          action: 'platform:capability:propose',
          input: {
            definition: {
              apiVersion: 'platform.starterkit.dev/v1alpha1',
              kind: 'CapabilityDefinition',
              metadata: '${{ parameters.metadata }}',
              spec: Object.fromEntries(
                ['purpose', 'interface', 'guardrails', 'acceptance', ...optional].map(s => [
                  s,
                  `\${{ parameters.${s} }}`,
                ]),
              ),
            },
          },
        },
      ],
      output: {
        links: [
          { title: 'Pull request', url: '${{ steps.propose.output.pullRequestUrl }}' },
          { title: 'Proposed capability in the catalog', entityRef: '${{ steps.propose.output.entityRef }}' },
        ],
        text: [
          {
            title: 'Next',
            content:
              'An agent builds the capability on the same branch with the `build-platform-capability` skill ' +
              '(in Claude Code: *"build the capability in ${{ steps.propose.output.pullRequestUrl }}"*). ' +
              'CI checks it against your definition and a person on the platform team validates it before merging.',
          },
        ],
      },
    },
  };
}

/** A capability definition waiting in an open pull request. */
export function proposalEntity(
  definition: { metadata: { name: string; title: string; owner: string }; spec: any },
  pr: { number: number; url: string; title: string; author: string },
): Entity {
  const { metadata, spec } = definition;
  const guardrails = [...(spec.guardrails?.everyone ?? []), ...(spec.guardrails?.agents ?? [])];
  return {
    apiVersion: 'backstage.io/v1alpha1',
    kind: 'Resource',
    metadata: {
      name: `${metadata.name}.pr-${pr.number}`,
      title: `${metadata.title} (proposed, PR #${pr.number})`,
      description:
        `${spec.purpose?.problem ?? ''} Proposed by ${pr.author}: ${spec.interface?.kind} with ` +
        `${spec.interface?.parameters?.length ?? 0} parameters, ${guardrails.length} guardrails and ` +
        `${spec.acceptance?.length ?? 0} acceptance criteria.`,
      annotations: { ...managedBy(`proposal/${pr.number}`), [`${PREFIX}/pull-request`]: pr.url },
      tags: ['platform-capability', 'proposed'],
      links: [{ url: pr.url, title: `Pull request #${pr.number}` }],
    },
    spec: {
      type: 'platform-capability',
      lifecycle: 'proposed',
      owner: metadata.owner,
      system: 'internal-developer-platform',
    },
  };
}
