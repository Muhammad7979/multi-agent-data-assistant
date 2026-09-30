export type AssistantResponse = {
  answer: string;
  route: 'sql' | 'etl' | 'policy';
  status: 'answered' | 'declined' | 'insufficient_evidence';
  sources?: { source_id: number; document_id: string; filename: string; page: number | null; section: string | null }[];
  files?: { id: string; filename: string; format: 'csv' | 'json' | 'parquet'; created_at: string; size_bytes: number; row_count: number | null }[];
  etl_status?: 'completed' | 'partial' | 'failed' | 'response_failed';
};
export type TableSummary = { id: string; label: string };
export type ETLFile = {
  id: string; filename: string; display_name: string; format: string;
  created_at: string; size_bytes: number; row_count: number | null;
  status: 'ready' | 'failed'; available: boolean;
};
export type ETLFiles = { files: ETLFile[]; page: { limit: number; offset: number; has_more: boolean } };
export type ETLPreview = {
  format: 'csv' | 'json'; columns: string[]; rows: string[][]; text: string | null;
  truncated: boolean; validation: 'preview_only' | 'unvalidated_prefix';
};
export type PolicyDocument = {
  id: string; name: string; type: string; status: 'pending' | 'processing' | 'ready' | 'failed';
  created_at: string; updated_at: string; size_bytes: number; chunk_count: number;
  has_indexed_version: boolean; error_code: string | null;
};
export type PolicyDocuments = { documents: PolicyDocument[]; page: { limit: number; offset: number; has_more: boolean } };
export type Cell = string | number | boolean | null;
export type Column = {
  name: string;
  type: 'string' | 'integer' | 'number' | 'boolean' | 'date' | 'datetime' | 'json';
};
export type TableRows = {
  table_id: string;
  columns: Column[];
  rows: Cell[][];
  page: { limit: number; offset: number; has_more: boolean };
};
