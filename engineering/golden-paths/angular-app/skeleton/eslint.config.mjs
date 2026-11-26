import eslint from '@eslint/js';
import angular from 'angular-eslint';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    files: ['**/*.ts'],
    extends: [eslint.configs.recommended, ...tseslint.configs.recommended, ...angular.configs.tsRecommended],
    processor: angular.processInlineTemplates,
    rules: {
      '@angular-eslint/prefer-standalone': 'error',
      '@angular-eslint/prefer-on-push-component-change-detection': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      'no-restricted-imports': ['error', { paths: [
        { name: '@angular/forms', importNames: ['UntypedFormBuilder', 'UntypedFormControl', 'UntypedFormGroup', 'UntypedFormArray'], message: 'Use typed reactive forms.' },
        { name: '@ngrx/store', message: 'Global NgRx Store requires an approved architecture decision.' },
        { name: '@ngrx/effects', message: 'Global NgRx Effects require an approved architecture decision.' }
      ] }]
    }
  },
  {
    files: ['**/*.html'],
    extends: [...angular.configs.templateRecommended, ...angular.configs.templateAccessibility]
  },
  { ignores: ['dist/**', 'coverage/**', 'node_modules/**'] }
);
