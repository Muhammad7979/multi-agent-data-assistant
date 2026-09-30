import ResultTable from '../../components/ResultTable';
import { DataEmpty, DataError, DataLoading } from '../../components/data/DataFeedback';
import TablePagination from '../../components/data/TablePagination';
import { useTableRows } from './useTableRows';

export default function TableRecords({ tableId, label, page, onPage }: { tableId: string; label: string; page: number; onPage: (page: number) => void }) {
  const { data, loading, error, receivedAt, refresh } = useTableRows(tableId, (page - 1) * 50);
  return <>
    <section className="data-panel records-panel" aria-label={`${label} records`} aria-busy={loading}>
      <div className="records-toolbar"><div><h2>Records</h2><span className="records-context">Read only · Ordered by record ID</span></div><button className="secondary" onClick={refresh} disabled={loading}>Refresh records</button></div>
      {loading ? <DataLoading>Loading {label.toLowerCase()} records…</DataLoading>
        : error ? <DataError title="Could not load records" message={error} retry={refresh} />
        : data && data.rows.length > 0 ? <ResultTable key={`${tableId}:${page}:${receivedAt?.getTime()}`} columns={data.columns} rows={data.rows} label={label} />
        : <DataEmpty title={page === 1 ? 'No records yet' : 'No records on this page'}><p>{page === 1 ? 'This table is available, but no records were returned.' : 'Records may have changed since this page was opened.'}</p>{page > 1 && <button className="secondary" onClick={() => onPage(1)}>Return to first page</button>}</DataEmpty>}
      <TablePagination page={page} count={data?.rows.length ?? null} loading={loading} hasMore={data?.page.has_more ?? false} onPage={onPage} />
    </section>
    <div className="records-footnote"><span>— means no value. Long values can be expanded.</span>{receivedAt && <span>Retrieved <time dateTime={receivedAt.toISOString()}>{receivedAt.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time> · local browser time</span>}</div>
  </>;
}
