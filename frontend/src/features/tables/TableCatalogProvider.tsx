import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { getTables } from '../../api';
import type { TableSummary } from '../../types';

type Catalog = { tables: TableSummary[]; loading: boolean; error: string; receivedAt: Date | null; refresh: () => void };
const TableCatalogContext = createContext<Catalog | null>(null);

export function TableCatalogProvider({ children }: { children: ReactNode }) {
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [receivedAt, setReceivedAt] = useState<Date | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    getTables(controller.signal).then(result => {
      if (!controller.signal.aborted) { setTables(result); setReceivedAt(new Date()); }
    }).catch(cause => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not load tables.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);

  return <TableCatalogContext.Provider value={{ tables, loading, error, receivedAt, refresh: () => setRevision(value => value + 1) }}>
    {children}
  </TableCatalogContext.Provider>;
}

export function useTableCatalog() {
  const catalog = useContext(TableCatalogContext);
  if (!catalog) throw new Error('Table catalog must be used inside its provider.');
  return catalog;
}
