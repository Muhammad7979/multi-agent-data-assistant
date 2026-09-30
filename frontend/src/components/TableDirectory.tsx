import { Link } from 'react-router';
import type { TableSummary } from '../types';
import Icon from './Icon';
import { navigationTables, tableIcon, tablePath } from '../features/tables/tableNavigation';

export default function TableDirectory({ tables }: { tables: TableSummary[] }) {
  return tables.length ? <ul className="table-directory">{navigationTables(tables).map(table => <li key={table.id}><Link to={tablePath(table.id)}>
    <span className="directory-icon"><Icon name={tableIcon(table.id)} /></span><span><strong>{table.label}</strong><small>{table.id}</small></span><span className="directory-arrow" aria-hidden="true">→</span>
  </Link></li>)}</ul> : <div className="empty-response"><h3>No tables available.</h3><p>The database has no approved tables to browse. This does not mean it has no other data.</p></div>;
}
