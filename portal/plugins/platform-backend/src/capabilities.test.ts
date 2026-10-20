import { readFileSync } from 'fs';
import { resolve } from 'path';
import YAML from 'yaml';
import {
  capabilityEntity,
  capabilityRequestEntity,
  newCapabilityTemplate,
  proposalEntity,
  requestTemplate,
  summarizeCapability,
} from './capabilities';
import { compact, definitionErrors, pullRequestBody } from './scaffolder';

const repo = resolve(__dirname, '../../../..');
const xrd = YAML.parse(readFileSync(`${repo}/capabilities/postgres-database/definition.yaml`, 'utf8'));
const definition = YAML.parse(readFileSync(`${repo}/capabilities/postgres-database/capability.yaml`, 'utf8'));
const schema = JSON.parse(
  readFileSync(`${repo}/capabilities/schema/capability-definition.schema.json`, 'utf8'),
);

describe('capabilities', () => {
  const cap = summarizeCapability(xrd);

  it('reads a capability from its XRD', () => {
    expect(cap).toMatchObject({
      name: 'postgres-database',
      kind: 'PostgresDatabase',
      plural: 'postgresdatabases',
      scope: 'Namespaced',
      title: 'PostgreSQL database',
      stage: 'experimental',
      cost: { small: '0.50', medium: '2.00', large: '8.00' },
    });
    expect(cap.parameters.size).toMatchObject({ enum: ['small', 'medium', 'large'], default: 'small' });
    expect(cap.guardrails).toHaveLength(3);
  });

  it('points the documentation at its folder in the platform repository', () => {
    const entity = capabilityEntity(cap, 'http://portal', 'http://git/platform/repo');
    expect(entity.metadata.annotations?.['backstage.io/techdocs-ref']).toBe(
      'url:http://git/platform/repo/src/branch/main/capabilities/postgres-database',
    );
    expect(entity.metadata.links?.map(l => l.title)).toEqual(['Request a PostgreSQL database', 'Documentation']);
  });

  it('builds the request form from the parameters', () => {
    const template = requestTemplate(cap, 'http://localhost:7007') as any;
    expect(template.metadata.name).toBe('request-postgres-database');
    const page = template.spec.parameters[0];
    expect(page.required).toEqual(['environment', 'name']);
    expect(page.properties.size).toMatchObject({ enum: ['small', 'medium', 'large'], default: 'small' });
    expect(page.properties.size.description).toContain('large 8.00 EUR');
    expect(template.spec.steps[0].input).toMatchObject({
      capability: 'PostgresDatabase',
      environment: '${{ parameters.environment }}',
      parameters: { size: '${{ parameters.size }}', version: '${{ parameters.version }}' },
    });
  });

  it('shows who requested what in the catalog', () => {
    const entity = capabilityRequestEntity(
      cap,
      {
        metadata: {
          name: 'orders-db',
          namespace: 'env-payments-dev',
          annotations: {
            'platform.starterkit.dev/requested-by': 'claude-code',
            'platform.starterkit.dev/requester-type': 'agent',
          },
        },
        spec: { size: 'small', crossplane: {} },
        status: { secretName: 'orders-db-connection', estimatedDailyCost: '0.50' },
      },
      new Map([['payments-dev', 'payments']]),
    ) as any;
    expect(entity.metadata.name).toBe('orders-db.payments-dev');
    expect(entity.metadata.description).toBe(
      'PostgreSQL database requested by agent claude-code. size small, 0.50 EUR/day.',
    );
    expect(entity.spec.owner).toBe('group:default/payments');
    expect(entity.spec.dependsOn).toEqual([
      'resource:default/postgres-database',
      'resource:default/payments-dev',
    ]);
  });

  it('builds the new capability form from the schema, one page per section', () => {
    const template = newCapabilityTemplate(schema) as any;
    const pages = template.spec.parameters.map((p: any) => p.title);
    expect(pages).toEqual([
      'Capability',
      'Purpose',
      'Interface',
      'Guardrails',
      'Acceptance criteria',
      'More (optional)',
    ]);
    const guardrails = template.spec.parameters[3].properties.guardrails;
    expect(guardrails.properties.agents.items.properties.enforcement.enum).toEqual(['deny', 'approval']);
    expect(JSON.stringify(template)).not.toContain('$ref');
  });

  it('accepts the example definition and explains what is wrong with a bad one', () => {
    expect(definitionErrors(schema, definition)).toEqual([]);
    const bad = structuredClone(definition);
    delete bad.spec.acceptance;
    bad.spec.guardrails.agents[0].enforcement = 'maybe';
    const errors = definitionErrors(schema, bad);
    expect(errors).toContain("/spec must have required property 'acceptance'");
    expect(errors.some(e => e.startsWith('/spec/guardrails/agents/0/enforcement'))).toBe(true);
  });

  it('drops what the form leaves empty', () => {
    expect(
      compact({ a: 'x', b: '', c: { d: undefined }, e: [], f: ['y', ''], g: '${{ parameters.lifecycle }}' }),
    ).toEqual({ a: 'x', f: ['y'] });
  });

  it('summarizes the definition in the pull request and in the catalog', () => {
    const body = pullRequestBody(definition, 'Ana');
    expect(body).toContain('**PostgreSQL database** (`PostgresDatabase`), proposed by Ana');
    expect(body).toContain('GR-3 (approval)');
    expect(body).toContain('AC-1, AC-2, AC-3, AC-4, AC-5, AC-6');
    const entity = proposalEntity(definition, {
      number: 3,
      url: 'http://localhost:3000/platform/platform-starter-kit/pulls/3',
      title: 't',
      author: 'ana',
    }) as any;
    expect(entity.metadata.name).toBe('postgres-database.pr-3');
    expect(entity.spec.lifecycle).toBe('proposed');
  });
});
