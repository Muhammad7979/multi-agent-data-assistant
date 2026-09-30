import type { Cell, Column } from '../../types';

export default function CellValue({ value, column }: { value: Cell; column: Column }) {
  if (value === null) return <span className="null-value" aria-label="No value (NULL)" title="No value (NULL)">—</span>;
  if (value === '') return <span className="null-value">Empty text</span>;
  if (typeof value === 'boolean') return <span className="badge">{value ? 'Yes' : 'No'}</span>;
  const text = String(value);
  // No numeric coercion: decimal and large-integer strings retain their precision.
  if (text.length > 100 || text.includes('\n')) return <details className="cell-details"><summary aria-label={`Expand or collapse ${column.name} value`}><span className="cell-preview">{text.slice(0, 80)}{text.length > 80 ? '…' : ''}</span><span className="cell-expand-label">Full value</span></summary><div tabIndex={0} role="region" aria-label={`Full ${column.name} value`}>{text}</div></details>;
  if (column.name === 'status' || column.name === 'payment_status') return <span className="badge record-status">{text}</span>;
  return <span className={`cell-text${column.type === 'date' || column.type === 'datetime' ? ' temporal-value' : ''}`}>{text}</span>;
}
