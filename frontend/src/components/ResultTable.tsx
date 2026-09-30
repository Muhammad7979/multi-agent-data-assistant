import type { Column, Cell } from '../types';
import CellValue from './data/CellValue';
import { columnLabel } from '../features/tables/tablePresentation';

export default function ResultTable({ columns, rows, label }: { columns: Column[]; rows: Cell[][]; label: string }) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label={`${label} records, scroll to view more columns`}>
    <table className="records-table"><caption className="sr-only">{label} records. Column order matches the database. Scroll horizontally for additional columns.</caption>
      <thead><tr>{columns.map((column, index) => <th scope="col" className={column.type === 'integer' || column.type === 'number' ? 'numeric-cell' : undefined} key={`${column.name}-${index}`} title={`Field: ${column.name}`}><span>{columnLabel(column.name)}</span><small>{column.type}</small></th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td className={columns[cellIndex].type === 'integer' || columns[cellIndex].type === 'number' ? 'numeric-cell' : undefined} key={cellIndex}>
        <CellValue value={cell} column={columns[cellIndex]} />
      </td>)}</tr>)}</tbody>
    </table>
  </div>;
}
