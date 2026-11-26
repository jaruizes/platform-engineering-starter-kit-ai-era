import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { normalizeLcov, sourceFile } from './normalize-lcov.mjs';

test('rewrites nested Angular Vitest paths to existing sources', () => {
  const root = mkdtempSync(join(tmpdir(), 'lcov-'));
  try {
    mkdirSync(join(root, 'src', 'app'), { recursive: true });
    writeFileSync(join(root, 'src', 'app', 'app.component.ts'), '');
    const input = 'TN:\\nSF:dist/test-out/run-42/src/app/app.component.ts\\nDA:1,1\\nend_of_record\\n'.replaceAll('\\n','\n');
    const actual = normalizeLcov(input, root);
    assert.ok(actual.includes('SF:src/app/app.component.ts\n'));
    assert.ok(actual.includes('DA:1,1'));
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test('rejects missing sources rather than claiming false coverage', () => {
  const root = mkdtempSync(join(tmpdir(), 'lcov-'));
  try { assert.throws(() => sourceFile('dist/test-out/run/src/app/missing.ts', root), /does not exist/); }
  finally { rmSync(root, { recursive: true, force: true }); }
});
