import { useCallback, useEffect, useRef, useState } from 'react';
import { deletePolicyDocument, getPolicyDocument, getPolicyDocuments, PolicyRequestError, uploadPolicyDocument } from '../api';
import type { PolicyDocument, PolicyDocuments } from '../types';
import Icon from '../components/Icon';
import { DataEmpty, DataError, DataLoading } from '../components/data/DataFeedback';
import TablePagination from '../components/data/TablePagination';
import PolicyDialog from '../features/policy/PolicyDialog';
import { dateLabel, statusExplanation, statusLabel, typeLabel, validatePolicyFile } from '../features/policy/policyPresentation';

export default function PolicyPage() {
  const [page, setPage] = useState(1);
  const [revision, refresh] = useState(0);
  const [catalog, setCatalog] = useState<PolicyDocuments | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [replacement, setReplacement] = useState<PolicyDocument | null>(null);
  const [busy, setBusy] = useState(false);
  const working = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [feedback, setFeedback] = useState('');
  const [operationError, setOperationError] = useState('');
  const [details, setDetails] = useState<PolicyDocument | null>(null);
  const [deleting, setDeleting] = useState<PolicyDocument | null>(null);
  const reload = useCallback(() => refresh(value => value + 1), []);
  const closeDetails = useCallback(() => setDetails(null), []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    getPolicyDocuments(page, controller.signal).then(result => {
      if (!controller.signal.aborted) setCatalog(result);
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Documents unavailable.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [page, revision]);
  const processing = catalog?.documents.some(doc => doc.status === 'pending' || doc.status === 'processing');
  useEffect(() => { if (!processing && !busy) return; const timer = window.setInterval(reload, 4000); return () => clearInterval(timer); }, [processing, busy, reload]);
  useEffect(() => {
    if (!details) return;
    const controller = new AbortController();
    getPolicyDocument(details.id, controller.signal).then(result => { if (!controller.signal.aborted) setDetails(result); })
      .catch(reason => { if (!controller.signal.aborted) setOperationError(reason instanceof Error ? reason.message : 'Details unavailable.'); });
    return () => controller.abort();
  }, [details?.id, revision]);
  async function mutate(action: () => Promise<void>) {
    if (working.current) return;
    working.current = true; setBusy(true); setOperationError(''); setFeedback('');
    try { await action(); }
    catch (reason) {
      setOperationError(reason instanceof PolicyRequestError && reason.document ? statusExplanation(reason.document) :
        `${reason instanceof Error ? reason.message : 'The operation failed.'} Refresh documents before retrying; server work may still be running.`);
    } finally { working.current = false; setBusy(false); reload(); }
  }
  function selectReplacement(doc: PolicyDocument) {
    setReplacement(doc); setFile(null); setFeedback(''); setOperationError('');
    if (fileInput.current) { fileInput.current.value = ''; fileInput.current.focus(); fileInput.current.scrollIntoView({ block: 'center' }); }
  }
  const validation = file ? validatePolicyFile(file) : null;
  return <section className="page data-page policy-page">
    <div className="page-heading"><div className="data-title"><span className="data-title-icon"><Icon name="policy" /></span><div><h1>Company Policy</h1><p className="intro">Manage the company documents used by the assistant to answer policy questions.</p></div></div><button className="secondary" disabled={loading} onClick={reload}>Refresh documents</button></div>
    <section className="data-panel policy-upload" aria-labelledby="policy-upload-title">
      <h2 id="policy-upload-title">{replacement ? `Replace ${replacement.name}` : 'Upload a document'}</h2>
      <p>{replacement ? 'Updated content will be re-indexed. The previous indexed version remains available until replacement succeeds.' : 'Upload UTF-8 TXT, Markdown (.md), or a text-based PDF. Maximum 10 MiB. Scanned and encrypted PDFs are not supported.'}</p>
      <form onSubmit={event => { event.preventDefault(); if (!file || validation) return; void mutate(async () => {
        const result = await uploadPolicyDocument(file, replacement?.id);
        setFeedback(statusExplanation(result)); setFile(null); setReplacement(null);
        if (fileInput.current) fileInput.current.value = '';
        setPage(1);
      }); }}>
        <label htmlFor="policy-file">{replacement ? 'Replacement file' : 'Document file'}</label>
        <input ref={fileInput} id="policy-file" type="file" accept=".txt,.md,.pdf" disabled={busy} aria-describedby="policy-file-feedback" aria-invalid={!!validation}
          onChange={event => { setFile(event.target.files?.[0] ?? null); setOperationError(''); setFeedback(''); }} />
        <p id="policy-file-feedback" role={validation ? 'alert' : undefined}>{validation ?? (file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KiB selected` : 'Choose one document to index.')}</p>
        <div className="policy-actions"><button className="primary" disabled={busy || !file || !!validation}>{busy ? 'Working…' : replacement ? 'Replace and re-index' : 'Upload and index'}</button>
          {replacement && <button type="button" className="secondary" disabled={busy} onClick={() => { setReplacement(null); setFile(null); if (fileInput.current) fileInput.current.value = ''; }}>Cancel replacement</button>}</div>
      </form>
      {busy && <p role="status"><span className="spinner" /> Uploading/indexing or completing your document change. Keep this page open; navigation does not cancel server work.</p>}
      {feedback && <p role="status">{feedback}</p>}
      {operationError && <div className="error" role="alert">{operationError}</div>}
    </section>
    <section className="data-panel" aria-label="Company documents" aria-busy={loading}>
      <div className="panel-heading"><h2>Documents</h2><span className="badge">Company knowledge</span></div>
      {error ? <DataError title="Could not load documents" message={error} retry={reload} /> : loading && !catalog ? <DataLoading>Loading documents…</DataLoading> : !catalog?.documents.length ?
        <DataEmpty title={page > 1 ? 'No documents on this page' : 'No company documents yet'}><p>Uploaded company documents become the assistant’s knowledge source for company-policy questions.</p></DataEmpty> :
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Policy document table"><table className="records-table policy-table"><thead><tr><th scope="col">Document</th><th scope="col">Status</th><th scope="col">Uploaded</th><th scope="col">Updated</th><th scope="col">Actions</th></tr></thead><tbody>
          {catalog.documents.map(doc => <tr key={doc.id}><td><strong>{doc.name}</strong><small>{typeLabel(doc.type)}</small></td><td><span className={`badge ${doc.status === 'failed' ? 'warning' : ''}`}>{statusLabel[doc.status]}</span></td><td>{dateLabel(doc.created_at)}</td><td>{dateLabel(doc.updated_at)}</td><td><div className="policy-actions">
            <button className="quiet" onClick={() => { setOperationError(''); setDetails(doc); }} aria-label={`Details for ${doc.name}`}>Details</button>
            <button className="quiet" disabled={busy || doc.status === 'pending' || doc.status === 'processing' || doc.error_code === 'DELETE_PENDING'} onClick={() => selectReplacement(doc)} aria-label={`Replace ${doc.name}`}>Replace</button>
            <button className="quiet" disabled={busy} onClick={() => { setOperationError(''); setDeleting(doc); }} aria-label={`Delete ${doc.name}`}>Delete</button>
          </div></td></tr>)}
        </tbody></table></div>}
      <TablePagination page={page} count={error ? null : catalog?.documents.length ?? null} loading={loading || busy} hasMore={catalog?.page.has_more ?? false} onPage={setPage} />
    </section>
    {details && <PolicyDialog title="Document details" close={closeDetails}><h3>{details.name}</h3><dl className="policy-details"><dt>Type</dt><dd>{typeLabel(details.type)}</dd><dt>Status</dt><dd>{statusLabel[details.status]}</dd><dt>Uploaded</dt><dd>{dateLabel(details.created_at)}</dd><dt>Updated</dt><dd>{dateLabel(details.updated_at)}</dd><dt>File size</dt><dd>{(details.size_bytes / 1024).toFixed(1)} KiB</dd></dl><p>{statusExplanation(details)}</p><p>Details describe the latest upload attempt. Original-file viewing and editing are not available.</p>{operationError && <p className="error" role="alert">{operationError}</p>}<button className="secondary" onClick={reload}>Refresh status</button></PolicyDialog>}
    {deleting && <PolicyDialog title="Delete document?" close={() => { if (!busy) setDeleting(null); }}><p><strong>{deleting.name}</strong> will be removed from the documents used for company-policy answers. This cannot be undone.</p>{operationError && <p className="error" role="alert">{operationError}</p>}<div className="policy-actions"><button className="secondary" disabled={busy} onClick={() => setDeleting(null)}>Cancel</button><button className="primary" disabled={busy} onClick={() => void mutate(async () => { await deletePolicyDocument(deleting.id); setDeleting(null); setFeedback('Document deleted.'); if (replacement?.id === deleting.id) setReplacement(null); })}>{busy ? 'Deleting…' : 'Delete document'}</button></div></PolicyDialog>}
  </section>;
}
