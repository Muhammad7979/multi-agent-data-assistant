import type { AssistantResponse, TableRows, TableSummary, PolicyDocument, PolicyDocuments, ETLFile, ETLFiles, ETLPreview } from './types';

// Defaults to Vite's same-origin proxy. Set an absolute API URL only when needed.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL?.trim() || '/api').replace(/\/+$/, '');

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

async function request(path: string, options?: RequestInit): Promise<unknown> {
  let response: Response;
  try { response = await fetch(`${API_BASE_URL}${path}`, options); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('Could not reach the API. Check that the local backend is running.');
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (object(body) && object(body.error) && typeof body.error.message === 'string') {
      if (path.startsWith('/policy/documents')) throw new PolicyRequestError(body.error.message,
        typeof body.error.code === 'string' ? body.error.code : '', isPolicyDocument(body.document) ? body.document : undefined);
      throw new Error(body.error.message);
    }
    throw new Error(`The API returned an unexpected response (${response.status}).`);
  }
  return body;
}

export class PolicyRequestError extends Error {
  constructor(message: string, public code: string, public document?: PolicyDocument) { super(message); }
}
function isPolicyDocument(value: unknown): value is PolicyDocument {
  return object(value) && ['id', 'name', 'type', 'created_at', 'updated_at'].every(key => typeof value[key] === 'string') &&
    ['pending', 'processing', 'ready', 'failed'].includes(String(value.status)) &&
    typeof value.has_indexed_version === 'boolean' && typeof value.size_bytes === 'number' &&
    typeof value.chunk_count === 'number' && (value.error_code === null || typeof value.error_code === 'string');
}
export async function getPolicyDocuments(page: number, signal?: AbortSignal): Promise<PolicyDocuments> {
  const body = await request(`/policy/documents?limit=50&offset=${(page - 1) * 50}`, { signal });
  if (!object(body) || !Array.isArray(body.documents) || !body.documents.every(isPolicyDocument) ||
      !object(body.page) || typeof body.page.has_more !== 'boolean' || body.page.limit !== 50 || body.page.offset !== (page - 1) * 50)
    throw new Error('The API returned an invalid document list.');
  return body as PolicyDocuments;
}
export async function getPolicyDocument(id: string, signal?: AbortSignal): Promise<PolicyDocument> {
  const body = await request(`/policy/documents/${encodeURIComponent(id)}`, { signal });
  if (!isPolicyDocument(body)) throw new Error('The API returned invalid document details.');
  return body;
}
export async function uploadPolicyDocument(file: File, id?: string): Promise<PolicyDocument> {
  const extension = file.name.split('.').pop()?.toLowerCase();
  const mime = extension === 'pdf' ? 'application/pdf' : extension === 'md' ? 'text/markdown' : 'text/plain';
  const body = await request(`/policy/documents${id ? `/${encodeURIComponent(id)}` : ''}`, {
    method: id ? 'PUT' : 'POST', headers: { 'X-Filename': file.name, 'Content-Type': mime }, body: file,
  });
  if (!isPolicyDocument(body)) throw new Error('The API returned invalid indexing status. Refresh documents before retrying.');
  return body;
}
export async function deletePolicyDocument(id: string): Promise<void> {
  await request(`/policy/documents/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export async function askAssistant(question: string): Promise<AssistantResponse> {
  const body = await request('/assistant', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }),
  });
  if (!object(body) || typeof body.answer !== 'string' || !body.answer.trim() ||
      (body.route !== 'sql' && body.route !== 'etl' && body.route !== 'policy') ||
      (body.status !== 'answered' && body.status !== 'declined' && body.status !== 'insufficient_evidence')) {
    throw new Error('The API returned an invalid assistant response.');
  }
  if (body.route === 'policy' && (body.status === 'declined' || !Array.isArray(body.sources) ||
      (body.status === 'answered' && body.sources.length === 0) ||
      (body.status === 'insufficient_evidence' && body.sources.length !== 0) ||
      !body.sources.every(source => object(source) && Number.isInteger(source.source_id) &&
        Number(source.source_id) > 0 && typeof source.document_id === 'string' && !!source.document_id.trim() && typeof source.filename === 'string' && !!source.filename.trim() &&
        (source.page === null || (Number.isInteger(source.page) && Number(source.page) > 0)) &&
        (source.section === null || typeof source.section === 'string')))) {
    throw new Error('The API returned invalid policy sources.');
  }
  if (body.route !== 'policy' && body.status === 'insufficient_evidence') {
    throw new Error('The API returned an invalid assistant status.');
  }
  if (body.files !== undefined && (body.route !== 'etl' || !Array.isArray(body.files) ||
      !body.files.every(file => object(file) && typeof file.id === 'string' && /^[0-9a-f]{16}$/.test(file.id) &&
        typeof file.filename === 'string' && typeof file.created_at === 'string' &&
        ['csv', 'json', 'parquet'].includes(String(file.format)) && Number.isInteger(file.size_bytes) && Number(file.size_bytes) >= 0 &&
        (file.row_count === null || (Number.isInteger(file.row_count) && Number(file.row_count) >= 0))))) {
    throw new Error('The API returned invalid ETL file metadata. Check file history before repeating extraction.');
  }
  return body as AssistantResponse;
}

export function etlFileUrl(id: string, action: 'preview' | 'download'): string {
  return `${API_BASE_URL}/etl/files/${encodeURIComponent(id)}/${action}`;
}

export async function getETLFiles(page: number, signal?: AbortSignal): Promise<ETLFiles> {
  const offset = (page - 1) * 50;
  const body = await request(`/etl/files?limit=50&offset=${offset}`, { signal });
  if (!object(body) || !Array.isArray(body.files) || !body.files.every(file => object(file) &&
      typeof file.id === 'string' && /^[0-9a-f]{16}$/.test(file.id) &&
      ['filename', 'display_name', 'format', 'created_at'].every(key => typeof file[key] === 'string') &&
      Number.isFinite(Date.parse(String(file.created_at))) && Number.isSafeInteger(file.size_bytes) && Number(file.size_bytes) >= 0 &&
      (file.row_count === null || (Number.isSafeInteger(file.row_count) && Number(file.row_count) >= 0)) &&
      (file.status === 'ready' || file.status === 'failed') && typeof file.available === 'boolean') ||
      !object(body.page) || body.page.limit !== 50 || body.page.offset !== offset || typeof body.page.has_more !== 'boolean')
    throw new Error('The API returned an invalid ETL file list.');
  return body as ETLFiles;
}

export async function getETLPreview(id: string, signal?: AbortSignal): Promise<ETLPreview> {
  const body = await request(`/etl/files/${encodeURIComponent(id)}/preview`, { signal });
  if (!object(body) || !['csv', 'json'].includes(String(body.format)) ||
      !Array.isArray(body.columns) || !body.columns.every(column => typeof column === 'string') ||
      !Array.isArray(body.rows) || !body.rows.every(row => Array.isArray(row) && row.length === (body.columns as unknown[]).length && row.every(cell => typeof cell === 'string')) ||
      (body.text !== null && typeof body.text !== 'string') || typeof body.truncated !== 'boolean' ||
      !['preview_only', 'unvalidated_prefix'].includes(String(body.validation)))
    throw new Error('The API returned an invalid file preview.');
  return body as ETLPreview;
}

export async function getETLFile(id: string, signal?: AbortSignal): Promise<ETLFile> {
  const body = await request(`/etl/files/${encodeURIComponent(id)}`, { signal });
  if (!object(body) || body.id !== id || typeof body.filename !== 'string' ||
      typeof body.display_name !== 'string' || typeof body.format !== 'string' ||
      typeof body.created_at !== 'string' || !Number.isFinite(Date.parse(body.created_at)) ||
      !Number.isSafeInteger(body.size_bytes) || Number(body.size_bytes) < 0 ||
      (body.row_count !== null && (!Number.isSafeInteger(body.row_count) || Number(body.row_count) < 0)) ||
      body.status !== 'ready' || body.available !== true)
    throw new Error('This ETL file is not available. Refresh file history before trying again.');
  return body as ETLFile;
}

export async function getTables(signal: AbortSignal): Promise<TableSummary[]> {
  const body = await request('/tables', { signal });
  if (!object(body) || !Array.isArray(body.tables) || !body.tables.every(
    table => object(table) && typeof table.id === 'string' && typeof table.label === 'string',
  )) throw new Error('The API returned an invalid table list.');
  return body.tables as TableSummary[];
}

export async function getRows(id: string, offset: number, signal: AbortSignal): Promise<TableRows> {
  const body = await request(`/tables/${encodeURIComponent(id)}/rows?limit=50&offset=${offset}`, { signal });
  const types = ['string', 'integer', 'number', 'boolean', 'date', 'datetime', 'json'];
  if (!object(body) || body.table_id !== id || !Array.isArray(body.columns) ||
      !body.columns.every(column => object(column) && typeof column.name === 'string' &&
        typeof column.type === 'string' && types.includes(column.type)) ||
      !Array.isArray(body.rows) || !body.rows.every(row => Array.isArray(row) && row.length === (body.columns as unknown[]).length &&
        row.every(cell => cell === null || ['string', 'number', 'boolean'].includes(typeof cell))) ||
      !object(body.page) || body.page.limit !== 50 || body.page.offset !== offset || typeof body.page.has_more !== 'boolean') {
    throw new Error('The API returned an invalid table page.');
  }
  return body as TableRows;
}
