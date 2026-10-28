import { ActionsRegistryService } from '@backstage/backend-plugin-api/alpha';
import { InputError, NotFoundError } from '@backstage/errors';
import { CatalogService } from '@backstage/plugin-catalog-node';
import fs from 'node:fs/promises';
import path from 'node:path';
import YAML from 'yaml';

/** The label a service uses to say which architecture (and version) it follows. */
export const ARCHITECTURE_LABEL = 'platform.starterkit.dev/architecture';
const COMMON = 'common';

export type Architecture = {
  id: string;
  title: string;
  layer: string;
  version: number;
  lifecycle: string;
  useFor: string;
  supersededBy?: string;
  template?: string;
  checkedBy?: string;
};

/** A document; `name` is `<architecture or common>/<document>`, for example backend-spring-v2/architecture-rules. */
export type Standard = { name: string; title: string; summary: string; architecture?: string };

export type SearchHit = {
  standard: string;
  architecture?: string;
  section: string;
  snippet: string;
  url: string;
  score: number;
};

/** Title and the text of the "## Purpose" section (or of the text after the title). */
export function describeStandard(name: string, markdown: string): Standard {
  const lines = markdown.split('\n');
  const title = lines.find(l => l.startsWith('# '))?.slice(2).trim() ?? name;
  const purpose = lines.findIndex(l => /^##\s+Purpose/i.test(l));
  const start = purpose >= 0 ? purpose + 1 : lines.findIndex(l => l.startsWith('# ')) + 1;
  const text: string[] = [];
  for (const line of lines.slice(start)) {
    if (line.startsWith('#') || line.startsWith('---') || line.startsWith('```')) break;
    if (line.trim()) text.push(line.trim());
  }
  return { name, title, summary: text.join(' ').replace(/\*\*/g, '') };
}

/** The anchor MkDocs gives a heading, so search results link to the right place in TechDocs. */
export function slugify(heading: string): string {
  return heading
    .replace(/[^\w\s-]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, '-');
}

/** Splits a document into its sections (one per heading), ignoring headings inside code blocks. */
export function splitSections(markdown: string): Array<{ heading: string; text: string }> {
  const sections: Array<{ heading: string; text: string[] }> = [];
  let current = { heading: '', text: [] as string[] };
  let inCode = false;
  for (const line of markdown.split('\n')) {
    if (line.startsWith('```')) inCode = !inCode;
    const heading = !inCode && /^#{1,6}\s+(.*)$/.exec(line);
    if (heading) {
      sections.push(current);
      current = { heading: heading[1].trim(), text: [] };
    } else if (inCode || !/^-{3,}\s*$/.test(line)) {
      current.text.push(line);
    }
  }
  sections.push(current);
  return sections
    .map(s => ({ heading: s.heading, text: s.text.join('\n').trim() }))
    .filter(s => s.heading && s.text);
}

const STOPWORDS = new Set(
  'a an and are as at be by can do does for from how i in is it must not of on or should that the this to what when where which with'.split(' '),
);
const tokenize = (text: string) =>
  (text.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(t => t.length > 1 && !STOPWORDS.has(t));

/**
 * The engineering standards: documents shared by every architecture
 * (docs/common) and the documents of each architecture version (docs/<id>),
 * described in architectures.yaml.
 */
export class StandardsLibrary {
  constructor(
    private readonly root: string,
    private readonly docsUrl = 'http://localhost:7007/docs/default/component/engineering-standards',
  ) {}

  async architectures(): Promise<Architecture[]> {
    const manifest = YAML.parse(await fs.readFile(path.join(this.root, 'architectures.yaml'), 'utf8'));
    return manifest?.architectures ?? [];
  }

  async architecture(id: string): Promise<Architecture> {
    const all = await this.architectures();
    const found = all.find(a => a.id === id);
    if (!found) {
      throw new NotFoundError(`No architecture '${id}'. Available: ${all.map(a => a.id).join(', ')}`);
    }
    return found;
  }

  /** The common documents and those of one architecture, or of all of them. */
  async standards(architecture?: string): Promise<Standard[]> {
    const ids = architecture
      ? [(await this.architecture(architecture)).id]
      : (await this.architectures()).map(a => a.id);
    const result: Standard[] = [];
    for (const folder of [COMMON, ...ids]) {
      const dir = path.join(this.root, 'docs', folder);
      const files = (await fs.readdir(dir).catch(() => [] as string[])).filter(f => f.endsWith('.md')).sort();
      for (const file of files) {
        const standard = describeStandard(
          `${folder}/${file.replace(/\.md$/, '')}`,
          await fs.readFile(path.join(dir, file), 'utf8'),
        );
        result.push(folder === COMMON ? standard : { ...standard, architecture: folder });
      }
    }
    return result;
  }

  /**
   * Finds a document by its full name (backend-spring-v2/architecture-rules),
   * or by its short name with an architecture, or by a short name only one
   * document has. Never guesses between architectures.
   */
  async find(name: string, architecture?: string): Promise<Standard> {
    const all = await this.standards();
    const exact = all.find(s => s.name === name || (architecture && s.name === `${architecture}/${name}`));
    if (exact) return exact;
    const matches = all.filter(s => s.name.endsWith(`/${name}`) && (!architecture || s.architecture === architecture || !s.architecture));
    if (matches.length === 1) return matches[0];
    if (matches.length > 1) {
      throw new InputError(
        `'${name}' exists for several architectures: ${matches.map(s => s.name).join(', ')}. ` +
          'Say which one (get-standards-for-entity tells you the architecture of a service).',
      );
    }
    throw new NotFoundError(`No standard named '${name}'. Available: ${all.map(s => s.name).join(', ')}`);
  }

  async read(standard: Standard): Promise<string> {
    return fs.readFile(path.join(this.root, 'docs', `${standard.name}.md`), 'utf8');
  }

  url(standard: string, heading?: string) {
    return `${this.docsUrl}/${standard}/${heading ? `#${slugify(heading)}` : ''}`;
  }

  /** Keyword search over the sections of the documents (BM25), with the architecture of each result. */
  async search(query: string, options: { architecture?: string; limit?: number } = {}): Promise<SearchHit[]> {
    const terms = [...new Set(tokenize(query))];
    if (!terms.length) throw new InputError('Search for at least one word.');
    const sections: Array<{ standard: Standard; heading: string; text: string; tokens: string[] }> = [];
    for (const standard of await this.standards(options.architecture)) {
      for (const section of splitSections(await this.read(standard))) {
        sections.push({ standard, ...section, tokens: tokenize(`${section.heading} ${section.text}`) });
      }
    }
    const average = sections.reduce((sum, s) => sum + s.tokens.length, 0) / Math.max(sections.length, 1);
    const documentFrequency = new Map(terms.map(t => [t, sections.filter(s => s.tokens.includes(t)).length]));
    const scored = sections.map(section => {
      let score = 0;
      for (const term of terms) {
        const frequency = section.tokens.filter(t => t === term).length;
        if (!frequency) continue;
        const df = documentFrequency.get(term) ?? 0;
        const idf = Math.log(1 + (sections.length - df + 0.5) / (df + 0.5));
        score += (idf * frequency * 2.2) / (frequency + 1.2 * (0.25 + (0.75 * section.tokens.length) / average));
        if (tokenize(section.heading).includes(term)) score += idf;
      }
      return { section, score };
    });
    return scored
      .filter(s => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, options.limit ?? 5)
      .map(({ section, score }) => ({
        standard: section.standard.name,
        architecture: section.standard.architecture,
        section: section.heading,
        snippet: snippet(section.text, terms),
        url: this.url(section.standard.name, section.heading),
        score: Math.round(score * 100) / 100,
      }));
  }
}

function snippet(text: string, terms: string[], length = 400): string {
  const flat = text.replace(/\s+/g, ' ');
  const lower = flat.toLowerCase();
  const at = Math.min(...terms.map(t => lower.indexOf(t)).filter(i => i >= 0), flat.length);
  const start = Math.max(0, at - 80);
  return `${start > 0 ? '…' : ''}${flat.slice(start, start + length)}${start + length < flat.length ? '…' : ''}`;
}

/**
 * The engineering standards as MCP tools, so agents read the same documents
 * people read in TechDocs, in the version that applies to the service they
 * are changing, before they design or write code.
 */
export function registerStandardsActions(
  actionsRegistry: ActionsRegistryService,
  library: StandardsLibrary,
  catalog: CatalogService,
) {
  const architectureSchema = (z: any) =>
    z.object({
      id: z.string(),
      title: z.string(),
      layer: z.string(),
      version: z.number(),
      lifecycle: z.string(),
      useFor: z.string(),
      supersededBy: z.string().optional(),
      template: z.string().optional(),
      checkedBy: z.string().optional(),
    });
  const standardSchema = (z: any) =>
    z.object({ name: z.string(), title: z.string(), summary: z.string(), architecture: z.string().optional() });

  actionsRegistry.register({
    name: 'list-engineering-standards',
    title: 'List the engineering standards',
    description:
      'Lists the architectures services can follow (several versions coexist: backend v1 and v2, ' +
      'Angular and React frontends) and the documents that say how to build them: common ' +
      'documents for every architecture, and the architecture, rules and examples of each one. ' +
      'To change an existing service, call get-standards-for-entity first: it tells you which ' +
      'architecture that service follows. They apply to AI-generated code exactly as to human code.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z =>
        z.object({
          architecture: z.string().optional().describe('Only this architecture, for example frontend-react-v1'),
        }),
      output: z =>
        z.object({ architectures: z.array(architectureSchema(z)), standards: z.array(standardSchema(z)) }),
    },
    action: async ({ input }) => {
      const architectures = await library.architectures();
      return {
        output: {
          architectures: input.architecture
            ? architectures.filter(a => a.id === input.architecture)
            : architectures,
          standards: await library.standards(input.architecture),
        },
      };
    },
  });

  actionsRegistry.register({
    name: 'get-standards-for-entity',
    title: 'Get the standards that apply to a service',
    description:
      'Returns the architecture (and version) a catalog entity follows, from its ' +
      `${ARCHITECTURE_LABEL} label, and the documents to read before changing it, in order. ` +
      'Warns when the architecture is deprecated and says what replaces it.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z =>
        z.object({
          entityRef: z.string().describe('Catalog entity, for example component:default/orders-api'),
        }),
      output: z =>
        z.object({
          entityRef: z.string(),
          architecture: architectureSchema(z),
          warning: z.string().optional(),
          read: z.array(standardSchema(z)),
        }),
    },
    action: async ({ input, credentials }) => {
      const entity = await catalog.getEntityByRef(input.entityRef, { credentials });
      if (!entity) throw new NotFoundError(`No entity '${input.entityRef}' in the catalog.`);
      const id = entity.metadata.labels?.[ARCHITECTURE_LABEL];
      if (!id) {
        const ids = (await library.architectures()).map(a => a.id).join(', ');
        throw new NotFoundError(
          `${input.entityRef} does not declare an architecture (label ${ARCHITECTURE_LABEL}). ` +
            `Ask its owner which one it follows: ${ids}.`,
        );
      }
      const architecture = await library.architecture(id);
      const standards = await library.standards(id);
      // Its own rules first, then its architecture and examples, then the common documents.
      const order = (s: Standard) =>
        s.architecture ? ['architecture-rules', 'architecture', 'examples'].indexOf(s.name.split('/')[1]) : 10;
      return {
        output: {
          entityRef: input.entityRef,
          architecture,
          warning:
            architecture.lifecycle === 'deprecated'
              ? `${architecture.title} is deprecated: follow its rules for changes to this service, ` +
                `do not use it for new code elsewhere${architecture.supersededBy ? `; new services use ${architecture.supersededBy}` : ''}.`
              : undefined,
          read: standards.sort((a, b) => order(a) - order(b)),
        },
      };
    },
  });

  actionsRegistry.register({
    name: 'get-engineering-standard',
    title: 'Read an engineering standard',
    description:
      'Returns the full Markdown of one engineering standard, by its full name (for example ' +
      'backend-spring-v2/architecture-rules or common/testing), or by its short name and ' +
      'architecture. Use list-engineering-standards or get-standards-for-entity to see the names.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z =>
        z.object({
          name: z.string().describe('Standard name, for example backend-spring-v2/architecture-rules'),
          architecture: z.string().optional().describe('Architecture, when the name is short'),
        }),
      output: z =>
        z.object({
          name: z.string(),
          title: z.string(),
          architecture: z.string().optional(),
          url: z.string(),
          markdown: z.string(),
        }),
    },
    action: async ({ input }) => {
      const standard = await library.find(input.name, input.architecture);
      return {
        output: {
          name: standard.name,
          title: standard.title,
          architecture: standard.architecture,
          url: library.url(standard.name),
          markdown: await library.read(standard),
        },
      };
    },
  });

  actionsRegistry.register({
    name: 'search-engineering-standards',
    title: 'Search the engineering standards',
    description:
      'Searches every section of the engineering standards and returns the best matches with ' +
      'their document, architecture and a link. Pass the architecture of the service you are ' +
      'changing so results from other versions do not mix in. Read the whole document with ' +
      'get-engineering-standard when a result matters.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z =>
        z.object({
          query: z.string().describe('What you are looking for, for example "error handling in controllers"'),
          architecture: z.string().optional().describe('Only this architecture (plus the common documents)'),
          limit: z.number().int().min(1).max(20).optional(),
        }),
      output: z =>
        z.object({
          results: z.array(
            z.object({
              standard: z.string(),
              architecture: z.string().optional(),
              section: z.string(),
              snippet: z.string(),
              url: z.string(),
              score: z.number(),
            }),
          ),
        }),
    },
    action: async ({ input }) => ({
      output: { results: await library.search(input.query, input) },
    }),
  });
}
