#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import process from 'node:process';
import { lint as markdownlint } from 'markdownlint/promise';

const EXCLUDED_PREFIXES = [
  '_bmad/',
  'node_modules/',
  'reference/',
  'src/bmad/',
];

function normalize(filePath) {
  return filePath.replace(/\\/g, '/');
}

function shouldExclude(filePath) {
  const normalized = normalize(filePath);
  return EXCLUDED_PREFIXES.some((prefix) => normalized.startsWith(prefix));
}

let files = process.argv
  .slice(2)
  .filter((file) => file.endsWith('.md') || file.endsWith('.markdown'))
  .filter((file) => !shouldExclude(file));

if (files.length === 0) {
  try {
    files = execFileSync('git', ['ls-files', '*.md', '*.markdown'], {
      encoding: 'utf8',
    })
      .split('\n')
      .filter(Boolean);
  } catch {
    files = [];
  }
}

files = files
  .map((file) => file.trim())
  .filter(Boolean)
  .filter((file) => !shouldExclude(file))
  .filter((file) => existsSync(file));

if (files.length === 0) {
  process.exit(0);
}

const config = {
  default: true,
  MD007: false,
  MD012: false,
  MD013: false,
  MD022: false,
  MD023: false,
  MD024: false,
  MD025: false,
  MD026: false,
  MD029: false,
  MD031: false,
  MD032: false,
  MD033: false,
  MD034: false,
  MD036: false,
  MD038: false,
  MD040: false,
  MD041: false,
  MD047: false,
  MD060: false,
};

try {
  const results = await markdownlint({
    files,
    config,
  });
  const output = results.toString();
  if (output) {
    process.stderr.write(`${output}\n`);
    process.exit(1);
  }
} catch (error) {
  process.stderr.write(`markdownlint library hook failed: ${error.message}\n`);
  process.exit(1);
}
