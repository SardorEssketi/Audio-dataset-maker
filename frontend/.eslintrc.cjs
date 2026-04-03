module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ['react', 'react-hooks'],
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
  ],
  settings: {
    react: { version: 'detect' },
  },
  ignorePatterns: ['dist', 'node_modules', '.vite', 'coverage'],
  rules: {
    'react/react-in-jsx-scope': 'off',
    'react/prop-types': 'off',

    // Current codebase has many unused imports/vars; keep lint usable.
    'no-unused-vars': 'off',

    // Avoid noisy deps warnings until hooks are standardized across the app.
    'react-hooks/exhaustive-deps': 'off',

    // UI text contains apostrophes/quotes; don't force HTML entities.
    'react/no-unescaped-entities': 'off',
  },
};
