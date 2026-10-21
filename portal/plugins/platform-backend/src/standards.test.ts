import fs from 'node:fs';
import path from 'node:path';
import YAML from 'yaml';
import { describeStandard, slugify, splitSections, StandardsLibrary } from './standards';

const root = path.resolve(__dirname, '../../../../standards');
const library = new StandardsLibrary(root, 'http://portal/docs');

describe('describeStandard', () => {
  it('uses the title and the purpose paragraph', () => {
    const markdown =
      '# Architecture Rules\n\n## Purpose\n\nThis document defines\nthe **rules**.\n\nFor everyone.\n\n---\n\n# Rules\n';
    expect(describeStandard('architecture-rules', markdown)).toEqual({
      name: 'architecture-rules',
      title: 'Architecture Rules',
      summary: 'This document defines the rules. For everyone.',
    });
  });
});

describe('the standards shipped with the kit', () => {
  it('has the documents of every architecture, with a title and a summary', async () => {
    const architectures = await library.architectures();
    expect(architectures.map(a => a.id)).toEqual([
      'backend-spring-v2',
      'backend-spring-v1',
      'frontend-angular-v1',
      'frontend-react-v1',
    ]);
    const standards = await library.standards();
    for (const { id } of architectures) {
      expect(standards.filter(s => s.architecture === id).map(s => s.name)).toEqual([
        `${id}/architecture-rules`,
        `${id}/architecture`,
        `${id}/examples`,
      ]);
    }
    for (const standard of standards) {
      expect(standard.title).not.toEqual(standard.name);
      expect(standard.summary.length).toBeGreaterThan(20);
    }
  });

  it('registers every architecture in the catalog and in the TechDocs navigation', async () => {
    const entities = YAML.parseAllDocuments(fs.readFileSync(path.join(root, 'catalog-info.yaml'), 'utf8')).map(
      d => d.toJS(),
    );
    const mkdocs = fs.readFileSync(path.join(root, 'mkdocs.yml'), 'utf8');
    for (const architecture of await library.architectures()) {
      const entity = entities.find(e => e.metadata.name === architecture.id);
      expect(entity?.spec.lifecycle).toBe(architecture.lifecycle);
      expect(mkdocs).toContain(`${architecture.id}/architecture-rules.md`);
    }
  });
});

describe('finding a standard', () => {
  it('needs the architecture when several have a document with that name', async () => {
    await expect(library.find('architecture-rules')).rejects.toThrow(/several architectures/);
    expect((await library.find('architecture-rules', 'backend-spring-v1')).name).toBe(
      'backend-spring-v1/architecture-rules',
    );
    expect((await library.find('backend-spring-v2/examples')).architecture).toBe('backend-spring-v2');
    expect((await library.find('testing')).name).toBe('common/testing');
  });
});

describe('searching the standards', () => {
  it('splits documents by heading, ignoring code blocks', () => {
    const sections = splitSections('# A\n\ntext a\n\n```bash\n# not a heading\n```\n\n## B\n\ntext b\n');
    expect(sections.map(s => s.heading)).toEqual(['A', 'B']);
    expect(sections[0].text).toContain('# not a heading');
  });

  it('links to the heading in TechDocs', () => {
    expect(slugify('AAC-001 — Hexagonal Architecture')).toBe('aac-001-hexagonal-architecture');
  });

  it('only returns the architecture asked for, plus the common documents', async () => {
    const results = await library.search('transactions in the service layer', {
      architecture: 'backend-spring-v1',
      limit: 10,
    });
    expect(results.length).toBeGreaterThan(0);
    expect(results.every(r => !r.architecture || r.architecture === 'backend-spring-v1')).toBe(true);
    expect(results[0].url).toMatch(/^http:\/\/portal\/docs\/(backend-spring-v1|common)\/[a-z-]+\/#/);
  });

  it('finds a rule by its id', async () => {
    const [first] = await library.search('FR-001');
    expect(first.standard).toBe('frontend-react-v1/architecture-rules');
  });
});
