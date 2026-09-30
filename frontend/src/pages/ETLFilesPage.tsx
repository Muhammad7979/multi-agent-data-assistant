import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { getETLFiles } from '../api';
import ETLDownload from '../features/etl/ETLDownload';
import { useAssistant } from '../features/assistant/AssistantProvider';
import type { ETLFile, ETLFiles } from '../types';
import Icon from '../components/Icon';
import { DataEmpty, DataError, DataLoading } from '../components/data/DataFeedback';
import TablePagination from '../components/data/TablePagination';
import ETLPreviewPanel from '../features/etl/ETLPreviewPanel';

export default function ETLFilesPage() {
  const { filesRevision } = useAssistant();
  const [search, setSearch] = useSearchParams();
  const requested = Number(search.get('page') ?? 1);
  const page = Number.isSafeInteger(requested) && requested > 0 && requested <= Math.floor(Number.MAX_SAFE_INTEGER / 50) ? requested : 1;
  const [revision, refresh] = useState(0);
  const [catalog, setCatalog] = useState<ETLFiles | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<ETLFile | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const reload = () => { setSelected(null); setSearch({}); refresh(value => value + 1); };
  useEffect(() => {
    if (search.has('page') && search.get('page') !== String(page)) setSearch(page === 1 ? {} : { page: String(page) }, { replace: true });
  }, [page, search, setSearch]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setCatalog(null); setSelected(null);
    getETLFiles(page, controller.signal).then(result => {
      if (!controller.signal.aborted) setCatalog(result);
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'File history unavailable.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [page, revision, filesRevision]);
  return <section className="page data-page etl-page">
    <div className="page-heading"><div className="data-title"><span className="data-title-icon"><Icon name="files" /></span><div>
      <h1>ETL Files</h1><p className="intro">Browse, preview and download data extracted from external APIs.</p>
    </div></div><button className="secondary" disabled={loading} onClick={reload}>Refresh files</button></div>
    {selected && <ETLPreviewPanel key={selected.id} file={selected} close={() => { setSelected(null); trigger.current?.focus(); }} />}
    <section className="data-panel records-panel" aria-label="Generated ETL files" aria-busy={loading}>
      <div className="panel-heading"><h2>Generated files</h2><span className="badge">Newest first</span></div>
      {loading ? <DataLoading>Loading ETL files…</DataLoading>
        : error ? <DataError title="Could not load files" message={error} retry={reload} />
        : !catalog?.files.length ? <DataEmpty title={page > 1 ? 'No files on this page' : 'No ETL files yet'}><p>{page > 1 ? 'Return to the previous page or refresh to see the latest files.' : 'Ask the Data Agent to extract data from an external API. Generated files will appear here.'}</p></DataEmpty>
        : <div className="table-scroll" tabIndex={0} role="region" aria-label="ETL files, scroll for more columns"><table className="records-table etl-files-table">
          <thead><tr><th scope="col">File name</th><th scope="col">Type</th><th scope="col">Size</th><th scope="col">Created · local time</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead>
          <tbody>{catalog.files.map(file => {
            const ready = file.available && file.status === 'ready';
            return <tr key={file.id}><td><strong>{file.filename}</strong><small>{file.display_name}</small></td>
              <td><span className="badge">{file.format.toUpperCase()}</span></td>
              <td>{file.size_bytes < 1024 ? `${file.size_bytes} B` : file.size_bytes < 1048576 ? `${(file.size_bytes / 1024).toFixed(1)} KiB` : `${(file.size_bytes / 1048576).toFixed(1)} MiB`}</td>
              <td><time dateTime={file.created_at} title={file.created_at}>{new Date(file.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time></td>
              <td><span className={`badge ${ready ? '' : 'warning'}`}>{ready ? 'Ready' : 'Unavailable'}</span>{!ready && <small>File missing or changed</small>}</td>
              <td>{ready ? <div className="etl-actions"><button className="quiet" aria-label={`Preview ${file.filename}`} onClick={event => { trigger.current = event.currentTarget; setSelected(file); }}>Open / Preview</button>
                <ETLDownload id={file.id} filename={file.filename} /></div> : <span className="null-value">No actions available</span>}</td>
            </tr>;
          })}</tbody>
        </table></div>}
      <TablePagination page={page} count={catalog?.files.length ?? null} loading={loading} hasMore={!error && !!catalog?.page.has_more} onPage={next => setSearch(next === 1 ? {} : { page: String(next) })} />
    </section>
  </section>;
}
