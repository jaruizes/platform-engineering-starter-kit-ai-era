import fs from 'node:fs';
import path from 'node:path';
import { describeStandard } from './standards';

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

  it('describes every standard shipped with the kit', () => {
    const dir = path.resolve(__dirname, '../../../../standards/docs');
    for (const file of fs.readdirSync(dir).filter(f => f.endsWith('.md') && f !== 'index.md')) {
      const standard = describeStandard(file, fs.readFileSync(path.join(dir, file), 'utf8'));
      expect(standard.title).not.toEqual(file);
      expect(standard.summary.length).toBeGreaterThan(20);
    }
  });
});
