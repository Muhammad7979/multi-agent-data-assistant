// Dependency-free contract/render checks using the project's TypeScript compiler.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '..');
function load(file, mocks = {}) {
  const filename = path.join(root, file);
  const code = fs.readFileSync(filename, 'utf8').replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
  const module = new Module(filename);
  module.filename = filename;
  module.paths = Module._nodeModulePaths(path.dirname(filename));
  const original = module.require.bind(module);
  module.require = name => name in mocks ? mocks[name] : original(name);
  module._compile(ts.transpileModule(code, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022,
  } }).outputText, filename);
  return module.exports;
}
const api = load('src/api.ts');
const supported = { answer: 'Annual leave is **20 days**. [1]', route: 'policy', status: 'answered', sources: [
  { source_id: 1, document_id: 'a', filename: 'Employee Handbook.pdf', page: 12, section: null },
  { source_id: 2, document_id: 'b', filename: 'Remote Work Policy.pdf', page: null, section: 'Section 3' },
] };
test('SQL, ETL and Policy use the same POST without a route selector', async () => {
  for (const response of [{ answer: 'Two users', route: 'sql', status: 'answered' },
    { answer: 'ETL report', route: 'etl', status: 'answered' }, supported,
    { answer: "I couldn't find enough information.", route: 'policy', status: 'insufficient_evidence', sources: [] }]) {
    let calls = 0;
    global.fetch = async (url, options) => {
      calls++; assert.equal(url, '/api/assistant'); assert.equal(options.method, 'POST');
      assert.deepEqual(JSON.parse(options.body), { question: 'Question' });
      return { ok: true, json: async () => response };
    };
    assert.deepEqual(await api.askAssistant('Question'), response); assert.equal(calls, 1);
  }
});
test('invalid sources and inconsistent statuses are rejected', async () => {
  for (const response of [{ ...supported, sources: [] }, { ...supported, status: 'insufficient_evidence' },
    { ...supported, sources: [{ ...supported.sources[0], page: 0 }] },
    { ...supported, sources: [{ ...supported.sources[0], filename: '' }] }]) {
    global.fetch = async () => ({ ok: true, json: async () => response });
    await assert.rejects(api.askAssistant('Question'));
  }
});
test('provider errors are shown without retry', async () => {
  let calls = 0;
  global.fetch = async () => { calls++; return { ok: false, json: async () => ({ error: { message: 'Service unavailable' } }) }; };
  await assert.rejects(api.askAssistant('Question'), /Service unavailable/); assert.equal(calls, 1);
});
function render(response) {
  const state = { response, open: false, question: '', submittedQuestion: 'Question', loading: false, error: '' };
  const Panel = load('src/features/assistant/AssistantPanel.tsx', {
    './AssistantProvider': { useAssistant: () => state },
    '../../api': api,
    'react-router': { Link: ({ to, children, ...props }) => React.createElement('a', { href: to, ...props }, children) },
    '../etl/ETLDownload': { default: ({ id, filename }) => React.createElement('button', { 'data-file': id }, `Download ${filename}`), __esModule: true },
    '../../components/Icon': { default: () => null, __esModule: true },
    '../../components/layout/dialogFocus': { trapDialogFocus: () => {} },
    // Isolate the existing Markdown renderer; this test concerns panel composition.
    './AssistantMarkdown': { default: ({ text }) => React.createElement('div', { 'data-renderer': 'existing-markdown' }, text), __esModule: true },
  }).default;
  return renderToStaticMarkup(React.createElement(Panel));
}
test('Policy sources render genuine metadata below the existing Markdown renderer', () => {
  const html = render(supported);
  assert.ok(html.indexOf('existing-markdown') < html.indexOf('Policy sources'));
  assert.match(html, /Employee Handbook.pdf.*Page 12/);
  assert.match(html, /Remote Work Policy.pdf.*Section 3/);
  assert.doesNotMatch(html, /Page null|Page 0|Section null/);
});

test('stored ETL metadata uses the existing Markdown and download API without retry', async () => {
  const file = { id: '0123456789abcdef', filename: 'orders.csv', format: 'csv', created_at: '2026-09-30T00:00:00+00:00', size_bytes: 10, row_count: 1 };
  const response = { answer: 'Extraction completed; output saved successfully.', route: 'etl', status: 'answered', etl_status: 'completed', files: [file] };
  let calls = 0;
  global.fetch = async () => { calls++; return { ok: true, json: async () => response }; };
  assert.deepEqual(await api.askAssistant('Extract'), response);
  assert.equal(calls, 1);
  const html = render(response);
  assert.match(html, /existing-markdown/);
  assert.match(html, /\/etl\/files\/0123456789abcdef/);
  assert.doesNotMatch(html, /not verified completion/);
  global.fetch = async () => ({ ok: true, json: async () => ({ ...response, files: [{ ...file, id: '../private' }] }) });
  await assert.rejects(api.askAssistant('Extract'), /invalid ETL file metadata/);
});
test('insufficient evidence stays verbatim; SQL and ETL retain their presentation', () => {
  const html = render({ answer: 'No company evidence available.', route: 'policy', status: 'insufficient_evidence', sources: [] });
  assert.match(html, /No company evidence available/); assert.match(html, /Insufficient evidence/);
  assert.doesNotMatch(html, /Policy sources/);
  assert.doesNotMatch(render({ answer: 'SQL answer', route: 'sql', status: 'answered' }), /Policy sources|Experimental ETL/);
  assert.match(render({ answer: 'ETL answer', route: 'etl', status: 'answered' }), /Experimental ETL response/);
});
