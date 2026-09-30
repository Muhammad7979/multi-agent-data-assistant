export default function TablePagination({ page, count, loading, hasMore, onPage }: {
  page: number; count: number | null; loading: boolean; hasMore: boolean; onPage: (page: number) => void;
}) {
  const start = (page - 1) * 50 + 1;
  return <nav className="pagination" aria-label="Record pages">
    <span aria-live="polite">{count === null ? '50 records per page' : count === 0 ? 'No records on this page' : `Records ${start.toLocaleString()}–${(start + count - 1).toLocaleString()}`}{count !== null && <span className="pagination-size"> · 50 per page</span>}</span>
    <div><button className="secondary" disabled={loading || page === 1} onClick={() => onPage(page - 1)}>← Previous</button><span className="page-number">Page {page.toLocaleString()}</span><button className="secondary" disabled={loading || !hasMore} onClick={() => onPage(page + 1)}>Next →</button></div>
  </nav>;
}
