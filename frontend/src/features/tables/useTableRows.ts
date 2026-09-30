import { useEffect, useState } from 'react';
import { getRows } from '../../api';
import type { TableRows } from '../../types';

type Result = { key: string; data: TableRows | null; error: string; receivedAt: Date | null };

export function useTableRows(tableId: string, offset: number) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const key = `${tableId}:${offset}:${revision}`;

  useEffect(() => {
    const controller = new AbortController();
    getRows(tableId, offset, controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ key, data, error: '', receivedAt: new Date() });
    }).catch(cause => {
      if (!controller.signal.aborted) setResult({ key, data: null, error: cause instanceof Error ? cause.message : 'Could not load records.', receivedAt: null });
    });
    return () => controller.abort();
  }, [tableId, offset, key]);

  // Responses and errors are only visible for the request that produced them.
  const current = result?.key === key ? result : null;
  return { data: current?.data ?? null, error: current?.error ?? '', receivedAt: current?.receivedAt ?? null,
    loading: !current, refresh: () => setRevision(value => value + 1) };
}
