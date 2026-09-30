import { Link, NavLink } from 'react-router';
import Icon from '../Icon';
import { useTableCatalog } from '../../features/tables/TableCatalogProvider';
import { navigationTables, tableIcon, tablePath } from '../../features/tables/tableNavigation';

export function Brand() {
  return <Link className="brand" to="/" aria-label="Data Agent home">
    <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M5 5h6a7 7 0 0 1 0 14H5V5Z" stroke="currentColor" strokeWidth="2.5" /><path d="M10 9v6" stroke="currentColor" strokeWidth="2.5" /></svg></span>
    <span>Data Agent<span className="brand-caption">Data workspace</span></span>
  </Link>;
}

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { tables, loading, error, refresh } = useTableCatalog();
  return <div className="sidebar-content">
    <div className="sidebar-brand" onClick={onNavigate}><Brand /></div>
    <nav className="sidebar-nav" aria-label="Main navigation">
      <NavLink className="nav-link" to="/" end onClick={onNavigate}><Icon name="home" />Home</NavLink>
      <NavLink className="nav-link" to="/policy" onClick={onNavigate}><Icon name="policy" />Company Policy</NavLink>
      <NavLink className="nav-link" to="/etl/files" onClick={onNavigate}><Icon name="files" />ETL Files</NavLink>
      <div className="nav-group-label">Data</div>
      <NavLink className="nav-link" to="/data" end onClick={onNavigate}><Icon name="table" />All tables</NavLink>
      {navigationTables(tables).map(table => <NavLink className="nav-link" key={table.id} to={tablePath(table.id)} onClick={onNavigate}>
        <Icon name={tableIcon(table.id)} /><span>{table.label}</span>
      </NavLink>)}
      {loading && <div className="nav-status" role="status"><span className="spinner" />Loading tables…</div>}
      {error && <div className="nav-status nav-error" role="alert"><span>Table navigation unavailable.</span><button className="quiet" onClick={refresh}>Try again</button></div>}
      {!loading && !error && tables.length === 0 && <p className="nav-status">No tables available.</p>}
    </nav>
    <div className="sidebar-footer"><span className="environment"><span aria-hidden="true" />Local development</span><p>Trusted development data only</p></div>
  </div>;
}
