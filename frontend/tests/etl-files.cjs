const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
function load(file, mocks = {}) {
  const filename = path.resolve(__dirname, '..', file);
  const module = new Module(filename);
  module.filename = filename;
  module.paths = Module._nodeModulePaths(path.dirname(filename));
  const original = module.require.bind(module);
  module.require = name => name in mocks ? mocks[name] : original(name);
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8').replace('import.meta.env.VITE_API_BASE_URL', 'undefined'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename);
  return module.exports;
}
const api = load('src/api.ts');
const file = { id: '0123456789abcdef', filename: 'test_orders.csv', display_name: 'test orders', format: 'csv', created_at: '2026-09-30T12:00:00+00:00', size_bytes: 20, row_count: 2, status: 'ready', available: true };
const catalog = files => ({ files, page: { limit: 50, offset: 0, has_more: false } });

test('list refresh uses real responses, pagination and cancellation signal', async () => {
  const signal = new AbortController().signal;
  let calls = 0;
  global.fetch = async (url, options) => {
    assert.equal(url, '/api/etl/files?limit=50&offset=0');
    assert.equal(options.signal, signal);
    return { ok: true, json: async () => catalog(calls++ ? [file] : []) };
  };
  assert.equal((await api.getETLFiles(1, signal)).files.length, 0);
  assert.equal((await api.getETLFiles(1, signal)).files[0].id, file.id);
  global.fetch = async url => {
    assert.equal(url, '/api/etl/files?limit=50&offset=50');
    return { ok: true, json: async () => ({ ...catalog([]), page: { limit: 50, offset: 50, has_more: false } }) };
  };
  await api.getETLFiles(2);
});
test('CSV/JSON previews validate content; malformed responses and safe API errors are handled', async () => {
  for (const preview of [
    { format: 'csv', columns: ['id'], rows: [['1']], text: null, truncated: false, validation: 'preview_only' },
    { format: 'json', columns: [], rows: [], text: '{"id":1}', truncated: true, validation: 'unvalidated_prefix' },
  ]) {
    global.fetch = async url => { assert.equal(url, `/api/etl/files/${file.id}/preview`); return { ok: true, json: async () => preview }; };
    assert.deepEqual(await api.getETLPreview(file.id), preview);
  }
  global.fetch = async () => ({ ok: true, json: async () => catalog([{ ...file, id: '../private' }]) });
  await assert.rejects(api.getETLFiles(1), /invalid ETL file list/);
  global.fetch = async () => ({ ok: false, json: async () => ({ error: { message: 'The registered ETL file is missing.' } }) });
  await assert.rejects(api.getETLPreview(file.id), /file is missing/);
  global.fetch = async () => { throw new TypeError('network'); };
  await assert.rejects(api.getETLFiles(1), /Could not reach the API/);
});

const feedback = load('src/components/data/DataFeedback.tsx');
function renderPage(files, { loading = false, error = '' } = {}) {
  const values = [0, files === null ? null : catalog(files), loading, error, null];
  const Page = load('src/pages/ETLFilesPage.tsx', {
    react: { ...React, useState: () => [values.shift(), () => {}], useEffect: () => {} },
    'react-router': { useSearchParams: () => [new URLSearchParams(), () => {}] },
    '../api': api,
    '../features/assistant/AssistantProvider': { useAssistant: () => ({ filesRevision: 0 }) },
    '../features/etl/ETLDownload': { default: ({ id, filename }) => React.createElement('button', { 'data-file': id }, `Download ${filename}`), __esModule: true }, '../components/Icon': { default: () => null, __esModule: true },
    '../components/data/DataFeedback': feedback,
    '../components/data/TablePagination': load('src/components/data/TablePagination.tsx'),
    '../features/etl/ETLPreviewPanel': { default: () => null, __esModule: true },
  }).default;
  return renderToStaticMarkup(React.createElement(Page));
}
test('page renders loading, empty, error, real file fields and missing-file states', () => {
  assert.match(renderPage(null, { loading: true }), /Loading ETL files/);
  assert.match(renderPage([]), /No ETL files yet/);
  assert.match(renderPage(null, { error: 'Backend unavailable' }), /role="alert".*Backend unavailable/s);
  const html = renderPage([file, { ...file, id: 'fedcba9876543210', filename: 'missing.csv', available: false, status: 'failed' }]);
  assert.match(html, /test_orders.csv/);
  assert.match(html, /20 B/);
  assert.match(html, /datetime="2026-09-30T12:00:00\+00:00"/i);
  assert.match(html, /File missing or changed/);
  assert.match(html, /data-file="0123456789abcdef"/);
  assert.doesNotMatch(html, /data-file="fedcba9876543210"/);
});

test('preview preserves escaped text and identifies incomplete JSON and unsupported formats', () => {
  const render = (format, preview, error = '') => {
    const values = [preview, error, false, 0];
    const Panel = load('src/features/etl/ETLPreviewPanel.tsx', {
      react: { ...React, useState: () => [values.shift(), () => {}], useEffect: () => {} },
      '../../api': api, '../../components/data/DataFeedback': feedback,
      './ETLDownload': { default: () => null, __esModule: true },
    }).default;
    return renderToStaticMarkup(React.createElement(Panel, { file: { ...file, format }, close() {} }));
  };
  assert.match(render('parquet', null), /Preview unavailable/);
  assert.match(render('json', { text: '<script>alert(1)</script>', validation: 'unvalidated_prefix' }), /&lt;script&gt;/);
  assert.match(render('json', { text: '{}', validation: 'unvalidated_prefix' }), /not been validated/);
  assert.match(render('csv', null, 'File is missing'), /File is missing/);
});

module.exports = { api };

test('file details verify readiness and preserve known record counts', async () => {
  global.fetch = async url => { assert.equal(url, `/api/etl/files/${file.id}`); return { ok: true, json: async () => file }; };
  assert.deepEqual(await api.getETLFile(file.id), file);
  global.fetch = async () => ({ ok: true, json: async () => ({ ...file, available: false }) });
  await assert.rejects(api.getETLFile(file.id), /not available/);
});

test('download checks readiness, preserves filename, and catches missing/network errors', async () => {
  const oldDocument = global.document;
  let clicked = 0;
  let appended = 0;
  const anchor = { click() { clicked++; }, remove() {} };
  global.document = { createElement: () => anchor, body: { append() { appended++; } } };
  try {
    for (const fails of [false, true]) {
      const states = [];
      const Download = load('src/features/etl/ETLDownload.tsx', {
        react: { ...React, useRef: () => ({ current: false }), useState: initial => [initial, value => states.push(value)] },
        '../../api': { ...api, getETLFile: async () => { if (fails) throw new Error('File missing or network unavailable'); return file; } },
      }).default;
      const element = Download({ id: file.id, filename: file.filename });
      await element.props.children[0].props.onClick();
      if (fails) assert.ok(states.includes('File missing or network unavailable'));
    }
    assert.equal(clicked, 1); assert.equal(appended, 1);
    assert.equal(anchor.href, `/api/etl/files/${file.id}/download`);
    assert.equal(anchor.download, file.filename);
  } finally { global.document = oldDocument; }
});
