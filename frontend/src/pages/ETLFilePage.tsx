import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { getETLFile } from '../api';
import type { ETLFile } from '../types';
import { DataError, DataLoading } from '../components/data/DataFeedback';
import ETLPreviewPanel from '../features/etl/ETLPreviewPanel';

export default function ETLFilePage() {
  const { fileId = '' } = useParams();
  const navigate = useNavigate();
  const [file, setFile] = useState<ETLFile | null>(null);
  const [error, setError] = useState('');
  const [revision, refresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setFile(null); setError('');
    getETLFile(fileId, controller.signal).then(result => { if (!controller.signal.aborted) setFile(result); })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'File unavailable.'); });
    return () => controller.abort();
  }, [fileId, revision]);
  return <section className="page data-page etl-page">
    <Link className="data-breadcrumb" to="/etl/files">ETL Files</Link><h1>File details</h1>
    {error ? <DataError title="File unavailable" message={error} retry={() => refresh(value => value + 1)} />
      : file ? <ETLPreviewPanel key={file.id} file={file} close={() => navigate('/etl/files')} />
      : <DataLoading>Loading file details…</DataLoading>}
  </section>;
}
