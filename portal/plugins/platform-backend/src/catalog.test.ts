import { appEntity, environmentEntity } from './catalog';
import { denialReason } from './kubernetes';

const environment = {
  metadata: {
    name: 'load-test',
    creationTimestamp: '2026-10-20T10:00:00Z',
    annotations: {
      'platform.starterkit.dev/requested-by': 'claude-code',
      'platform.starterkit.dev/requester-type': 'agent',
      'platform.starterkit.dev/approved-by': 'Ana (user:default/ana)',
      'kubectl.kubernetes.io/last-applied-configuration': '{}',
    },
  },
  spec: { team: 'checkout', purpose: 'Load test', size: 'large', ttlHours: 24 },
  status: {
    namespace: 'env-load-test',
    estimatedDailyCost: '12.00',
    conditions: [{ type: 'Ready', status: 'True' }],
  },
};

describe('catalog entities', () => {
  it('turns an environment into a Resource owned by its team', () => {
    const entity = environmentEntity(environment);
    expect(entity.kind).toBe('Resource');
    expect(entity.spec).toMatchObject({ type: 'environment', owner: 'group:default/checkout' });
    expect(entity.metadata.tags).toEqual(['requested-by-agent', 'size-large']);
    expect(entity.metadata.annotations).toMatchObject({
      'platform.starterkit.dev/approved-by': 'Ana (user:default/ana)',
      'platform.starterkit.dev/status': 'Ready',
      'platform.starterkit.dev/expires-at': '2026-10-21T10:00:00.000Z',
      'backstage.io/kubernetes-namespace': 'env-load-test',
    });
    // Only the platform annotations are copied.
    expect(entity.metadata.annotations).not.toHaveProperty(
      'kubectl.kubernetes.io/last-applied-configuration',
    );
  });

  it('turns a service into a Component that depends on its environment', () => {
    const app = {
      metadata: { name: 'checkout-api', namespace: 'env-load-test' },
      spec: { image: 'podinfo', replicas: 1 },
      status: { url: 'http://checkout-api.env-load-test.svc.cluster.local' },
    };
    const entity = appEntity(app, new Map([['load-test', 'checkout']]));
    expect(entity.metadata.name).toBe('checkout-api.load-test');
    expect(entity.spec).toMatchObject({
      owner: 'group:default/checkout',
      dependsOn: ['resource:default/load-test'],
    });
    expect(entity.metadata.annotations?.['platform.starterkit.dev/status']).toBe('Starting');
  });
});

describe('denialReason', () => {
  it('keeps only the policy message', () => {
    const body = JSON.stringify({
      message:
        'admission webhook "vpol.validate.kyverno.svc-fail" denied the request: ' +
        'Policy cost-guardrails failed: Cost guardrail: environments can live at most 72 hours.',
    });
    expect(denialReason(body)).toBe('Cost guardrail: environments can live at most 72 hours.');
  });
});
