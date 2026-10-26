import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'
import tseslint from 'typescript-eslint'

/**
 * Правила доступности включаем предупреждениями: их много, а чинить их нужно пофазно,
 * вместе с переводом экранов на UI-kit.
 */
const a11yWarnings = Object.fromEntries(
  Object.keys(jsxA11y.flatConfigs.recommended.rules).map((rule) => [rule, 'warn']),
)

export default tseslint.config(
  // schema.d.ts генерируется из ../openapi.json — руками не правится и не линтуется
  { ignores: ['dist/', 'src/api/schema.d.ts', '.tmp-npm-cache/'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: { 'react-hooks': reactHooks, 'jsx-a11y': jsxA11y },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...a11yWarnings,
      // Устаревшее правило: считает неправильной вложенную подпись <label><span/><input/></label>,
      // хотя это корректный HTML. Современная замена — label-has-associated-control.
      'jsx-a11y/label-has-for': 'off',
      'jsx-a11y/label-has-associated-control': 'warn',
      // Правило рассчитано на кастомные контролы: на нативных input внутри label даёт ложные срабатывания
      'jsx-a11y/control-has-associated-label': 'off',
    },
  },
  {
    // Скрипты репозитория выполняются в Node, а не в браузере
    files: ['scripts/**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.node,
    },
  },
)
