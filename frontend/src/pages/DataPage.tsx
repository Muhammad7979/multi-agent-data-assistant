import { useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import TableDirectory from '../components/TableDirectory';
import Icon from '../components/Icon';
import { DataEmpty, DataError, DataLoading } from '../components/data/DataFeedback';
import { useTableCatalog } from '../features/tables/TableCatalogProvider';
import { tableIcon } from '../features/tables/tableNavigation';
import { tableDescription } from '../features/tables/tablePresentation';
import TableRecords from '../features/tables/TableRecords';

export default function DataPage() {
  const { tableId } = useParams();
  const [search, setSearch] = useSearchParams();
  const rawPage = search.get('page');
  const requestedPage = Number(rawPage ?? '1');
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 && requestedPage <= Math.floor(Number.MAX_SAFE_INTEGER / 50) ? requestedPage : 1;
  const { tables, loading, error, refresh } = useTableCatalog();
  const selected = tables.find(table => table.id === tableId);
  useEffect(() => {
    if (rawPage !== null && rawPage !== String(page)) setSearch(page === 1 ? {} : { page: String(page) }, { replace: true });
  }, [rawPage, page, setSearch]);
  const goToPage = (next: number) => setSearch(next === 1 ? {} : { page: String(next) });

  return <section className="page data-page">
    {tableId && <Link className="data-breadcrumb" to="/data">All tables <span aria-hidden="true">/</span></Link>}
    <div className="page-heading"><div className="data-title"><span className="data-title-icon"><Icon name={selected ? tableIcon(selected.id) : 'table'} /></span><div>
      <h1>{tableId ? selected?.label ?? 'Table' : 'All tables'}</h1>
      <p className="intro">{selected ? tableDescription(selected.id) : tableId ? 'Browse available database records.' : 'Explore the data available in your workspace.'}</p>
    </div></div>{!tableId && <button className="secondary" disabled={loading} onClick={refresh}>Refresh tables</button>}</div>
    {selected?.id === 'public.payments' && <p className="data-context-note">Payment amounts are shown as stored. Currency information and payment totals are not provided.</p>}
    {loading && tables.length === 0 ? <div className="data-panel"><DataLoading>Loading table catalog...</DataLoading></div>
      : error ? <div className="data-panel"><DataError title="Could not load tables" message={error} retry={refresh} /></div>
      : !tableId ? <div className="data-panel"><div className="panel-heading"><h2>Available tables</h2><span className="badge">Read only</span></div><TableDirectory tables={tables} /></div>
      : !selected ? <div className="data-panel"><DataEmpty level={2} title="Table unavailable"><p>This table is not in the available catalog.</p><Link to="/data">Browse available tables</Link></DataEmpty></div>
      : <TableRecords key={selected.id} tableId={selected.id} label={selected.label} page={page} onPage={goToPage} />}
  </section>;
}
