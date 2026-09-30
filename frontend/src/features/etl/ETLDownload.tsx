import { useRef, useState } from 'react';
import { etlFileUrl, getETLFile } from '../../api';

export default function ETLDownload({ id, filename }: { id: string; filename: string }) {
  const working = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function download() {
    if (working.current) return;
    working.current = true; setBusy(true); setError('');
    try {
      const file = await getETLFile(id);
      // Keep large downloads in the browser's native streaming download manager.
      const link = document.createElement('a');
      link.href = etlFileUrl(file.id, 'download'); link.download = file.filename;
      link.target = '_blank'; link.rel = 'noopener noreferrer';
      document.body.append(link); link.click(); link.remove();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Download unavailable.'); }
    finally { working.current = false; setBusy(false); }
  }
  return <div className="etl-download"><button className="quiet" disabled={busy} aria-label={`Download ${filename}`} onClick={download}>{busy ? 'Checking file…' : 'Download'}</button>
    {error && <p className="error" role="alert">{error}</p>}</div>;
}
