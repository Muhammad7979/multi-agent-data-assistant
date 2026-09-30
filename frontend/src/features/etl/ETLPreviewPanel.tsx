import { useEffect, useRef, useState } from 'react';
import { getETLPreview } from '../../api';
import ETLDownload from './ETLDownload';
import type { ETLFile, ETLPreview } from '../../types';
import { DataEmpty, DataError, DataLoading } from '../../components/data/DataFeedback';

export default function ETLPreviewPanel({ file, close }: { file: ETLFile; close: () => void }) {
  const [preview, setPreview] = useState<ETLPreview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, refresh] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => {
    if (!['csv', 'json'].includes(file.format)) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true); setError(''); setPreview(null);
    getETLPreview(file.id, controller.signal).then(result => {
      if (!controller.signal.aborted) setPreview(result);
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Preview unavailable.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [file.id, file.format, revision]);
  return <section className="data-panel etl-preview" aria-labelledby="etl-preview-title" aria-busy={loading}>
    <div className="panel-heading"><h2 id="etl-preview-title" ref={heading} tabIndex={-1}>Preview: {file.filename}</h2>
      <button className="secondary" onClick={close}>Close preview</button></div>
    <dl className="etl-file-details">
      <dt>Description</dt><dd>{file.display_name || 'No description available'}</dd>
      <dt>Created</dt><dd><time dateTime={file.created_at} title={file.created_at}>{new Date(file.created_at).toLocaleString()} (local time)</time></dd>
      <dt>Format</dt><dd>{file.format.toUpperCase()}</dd>
      <dt>File size</dt><dd>{file.size_bytes.toLocaleString()} bytes</dd>
      {file.row_count !== null && <><dt>Records</dt><dd>{file.row_count.toLocaleString()}</dd></>}
    </dl>
    {error ? <DataError title="Could not preview file" message={error} retry={() => refresh(value => value + 1)} />
      : loading ? <DataLoading>Loading file preview…</DataLoading>
      : !['csv', 'json'].includes(file.format) ? <DataEmpty title="Preview unavailable"><p>This format is available as an original-file download.</p></DataEmpty>
      : preview?.format === 'csv' && preview.columns.length > 0 ?
        <div className="table-scroll" tabIndex={0} role="region" aria-label="CSV preview, scroll for more columns"><table className="records-table">
          <thead><tr>{preview.columns.map((column, index) => <th scope="col" key={index}>{column || '(Unnamed column)'}</th>)}</tr></thead>
          <tbody>{preview.rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column}>{cell === '' ? <span className="null-value">Empty</span> : cell}</td>)}</tr>)}</tbody>
        </table>{!preview.rows.length && <DataEmpty title="No data rows"><p>This file contains column headers only.</p></DataEmpty>}</div>
      : preview?.text ? <pre className="etl-text-preview" tabIndex={0} aria-label="JSON file preview">{preview.text}</pre>
      : <DataEmpty title="Empty file"><p>There is no content to preview.</p></DataEmpty>}
    <div className="etl-preview-footer">
      <p>{preview?.validation === 'unvalidated_prefix' ? 'Partial text preview. This prefix has not been validated as a complete JSON document.' : preview?.truncated ? 'Preview truncated. Download the original file for all content.' : 'Preview only; the remainder of the file has not been checked.'}</p>
      <ETLDownload id={file.id} filename={file.filename} />
      <p>Downloads contain the complete original file. Transfer progress and interruptions appear in your browser’s downloads.</p>
    </div>
  </section>;
}
