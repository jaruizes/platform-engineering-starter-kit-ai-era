import { ActionsRegistryService } from '@backstage/backend-plugin-api/alpha';
import { NotFoundError } from '@backstage/errors';
import fs from 'node:fs/promises';
import path from 'node:path';

export type Standard = { name: string; title: string; summary: string };

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

/**
 * The engineering standards as MCP tools, so agents read the same documents
 * people read in TechDocs before they design or write code.
 */
export function registerStandardsActions(actionsRegistry: ActionsRegistryService, dir: string) {
  const list = async () => {
    const files = (await fs.readdir(dir)).filter(f => f.endsWith('.md') && f !== 'index.md').sort();
    return Promise.all(
      files.map(async f =>
        describeStandard(f.replace(/\.md$/, ''), await fs.readFile(path.join(dir, f), 'utf8')),
      ),
    );
  };

  actionsRegistry.register({
    name: 'list-engineering-standards',
    title: 'List the engineering standards',
    description:
      'Lists the documents that say how services must be built here: architecture, architecture ' +
      'rules, technology policy, development rules and testing. Read the relevant ones with ' +
      'get-engineering-standard before designing or writing code. They apply to AI-generated code ' +
      'exactly as to human code.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z => z.object({}),
      output: z =>
        z.object({
          standards: z.array(z.object({ name: z.string(), title: z.string(), summary: z.string() })),
        }),
    },
    action: async () => ({ output: { standards: await list() } }),
  });

  actionsRegistry.register({
    name: 'get-engineering-standard',
    title: 'Read an engineering standard',
    description:
      'Returns the full Markdown of one engineering standard, for example architecture-rules or ' +
      'technology-policy. Use list-engineering-standards to see the names.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z =>
        z.object({
          name: z.string().describe('Standard name, for example architecture-rules'),
        }),
      output: z => z.object({ name: z.string(), title: z.string(), markdown: z.string() }),
    },
    action: async ({ input }) => {
      const known = await list();
      const standard = known.find(s => s.name === input.name);
      if (!standard) {
        throw new NotFoundError(
          `No standard named '${input.name}'. Available: ${known.map(s => s.name).join(', ')}`,
        );
      }
      const markdown = await fs.readFile(path.join(dir, `${standard.name}.md`), 'utf8');
      return { output: { name: standard.name, title: standard.title, markdown } };
    },
  });
}
