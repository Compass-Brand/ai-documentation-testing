let tsParser = null;

try {
  ({ default: tsParser } = await import('@typescript-eslint/parser'));
} catch {}

const baseConfig = [
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'bmad-builder/**',
      'bmad-method-test-architecture-enterprise/**',
      'bmad-module-creative-intelligence-suite/**',
      'bmad-method-wds-expansion/**',
      'BMAD-CYBERSEC/**',
      'ai-memory/**',
      'pov-oversight-agent/**',
      'BMAD-METHOD/**',
      '.beads/**',
      'reference/BMAD/research/**',
      '.codex/**',
      '.claude/**',
      '.opencode/**',
      '.serena/**',
    ],
    linterOptions: {
      reportUnusedDisableDirectives: 'off',
    },
  },
  {
    files: ['**/*.js', '**/*.mjs', '**/*.cjs'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        process: 'readonly',
        console: 'readonly',
        module: 'readonly',
        require: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
      },
    },
    rules: {
      'no-undef': 'error',
      'no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],
    },
  },
  {
    files: ['**/*.cjs'],
    languageOptions: {
      sourceType: 'commonjs',
    },
  },
];

const tsConfig = tsParser
  ? [
      {
        files: ['**/*.ts', '**/*.tsx'],
        languageOptions: {
          parser: tsParser,
          parserOptions: {
            ecmaVersion: 'latest',
            sourceType: 'module',
          },
          globals: {
            process: 'readonly',
            console: 'readonly',
            module: 'readonly',
            require: 'readonly',
            __dirname: 'readonly',
            __filename: 'readonly',
          },
        },
        rules: {
          'no-unused-vars': [
            'error',
            {
              argsIgnorePattern: '^_',
              varsIgnorePattern: '^_',
            },
          ],
        },
      },
    ]
  : [];

export default [...baseConfig, ...tsConfig];
