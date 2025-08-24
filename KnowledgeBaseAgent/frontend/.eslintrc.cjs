module.exports = {
  root: true,
  env: { 
    browser: true, 
    es2020: true,
    jest: true,
    node: true
  },
  extends: [
    'eslint:recommended',
    // '@typescript-eslint/recommended', // Temporarily disabled
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs', '**/*.css'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh', '@typescript-eslint'],
  rules: {
    'react-refresh/only-export-components': 'warn', // Downgrade to warning
    '@typescript-eslint/no-unused-vars': [
      'warn', // Change from error to warning
      { 
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        ignoreRestSiblings: true,
        destructuredArrayIgnorePattern: '^_'
      }
    ],
    '@typescript-eslint/no-explicit-any': 'warn', // Keep as warning
    'prefer-const': 'warn', // Change from error to warning
    'no-var': 'error', // Keep as error
    'no-unused-vars': 'off', // Turn off base rule
    'no-undef': 'off', // TypeScript handles this better
    'no-redeclare': 'off', // TypeScript handles this better
    'react-hooks/exhaustive-deps': 'warn', // Downgrade to warning
  },
  overrides: [
    {
      // Test files configuration
      files: ['**/*.test.{ts,tsx}', '**/__tests__/**/*.{ts,tsx}', '**/test/**/*.{ts,tsx}'],
      env: {
        jest: true,
      },
      globals: {
        jest: 'readonly',
        describe: 'readonly',
        it: 'readonly',
        expect: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        global: 'readonly',
      },
    },
  ],
}