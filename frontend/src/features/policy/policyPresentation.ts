import type { PolicyDocument } from '../../types';
export const statusLabel = { pending: 'Pending', processing: 'Processing', ready: 'Ready', failed: 'Failed' };
export const dateLabel = (value: string) => Number.isNaN(Date.parse(value)) ? 'Unavailable' : new Date(value).toLocaleString();
export const typeLabel = (value: string) => ({ 'text/plain': 'Text', 'text/markdown': 'Markdown', 'application/pdf': 'PDF' }[value.split(';')[0]] ?? value);
export function statusExplanation(document: PolicyDocument) {
  if (document.error_code === 'DELETE_PENDING') return 'Deletion is incomplete. This document is excluded from answers. Retry deletion.';
  if (document.status === 'ready') return 'Ready for company-policy questions in the assistant.';
  if (document.status === 'pending' || document.status === 'processing') return 'Indexing is not complete. Status updates automatically.';
  const reasons: Record<string, string> = {
    EMBEDDING_FAILED: 'The embedding provider could not process this document.', INDEXING_FAILED: 'The document could not be indexed.',
    NO_EXTRACTABLE_TEXT: 'No readable text was found. Scanned PDFs need a text-based version.',
    PARSING_FAILED: 'The document could not be read.', INVALID_TEXT_ENCODING: 'Use UTF-8 encoded text.',
    ENCRYPTED_PDF: 'Encrypted PDFs are not supported.', FILE_TOO_LARGE: 'The file exceeds the server upload limit.',
  };
  return `${reasons[document.error_code ?? ''] ?? 'Indexing did not complete.'}${document.has_indexed_version ? ' An indexed version remains available.' : ' This document is not available to the assistant.'}`;
}
export function validatePolicyFile(file: File): string | null {
  if (!/\.(txt|md|pdf)$/i.test(file.name)) return 'Choose a TXT, Markdown (.md), or text-based PDF file.';
  if (!file.size) return 'The selected file is empty.';
  if (file.size > 10 * 1024 * 1024) return 'Choose a file no larger than 10 MiB.';
  if (/[\x00-\x1f\x7f-\uffff/\\:<>"|?*]/.test(file.name) || file.name.trim() !== file.name || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])\./i.test(file.name))
    return 'Rename the file using plain letters, numbers, spaces, dots, hyphens or underscores.';
  return null;
}
