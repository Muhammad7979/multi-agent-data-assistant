import { useAssistant } from '../features/assistant/AssistantProvider';
import StatCard from '../components/dashboard/StatCard';
import ProviderUsageCard from '../components/dashboard/ProviderUsageCard';
import TableDirectory from '../components/TableDirectory';
import { useTableCatalog } from '../features/tables/TableCatalogProvider';

export default function HomePage() {
  const { openAssistant } = useAssistant();
  const { tables, loading, error, receivedAt, refresh } = useTableCatalog();
  const receipt = receivedAt && <time dateTime={receivedAt.toISOString()}>{receivedAt.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time>;
  return <section className="page home-page">
    <div className="page-heading"><div><div className="eyebrow">Workspace overview</div><h1>Home</h1>
      <p className="intro">Your available data and reporting, at a glance.</p></div>
      <div className="dashboard-actions"><button className="secondary" onClick={openAssistant}>Ask Data Agent</button><button className="secondary" disabled={loading} onClick={refresh}>Refresh overview</button></div>
    </div>
    <div className="dashboard-stats">
      <StatCard title="Available tables" icon="table" loading={loading} unavailable={!!error}
        value={error ? 'Unavailable' : tables.length.toLocaleString()}
        description="Approved tables returned by the database catalog. This is not a record count." />
      <StatCard title="Catalog retrieval" icon="table" loading={loading} unavailable={!!error}
        value={error ? 'Could not refresh' : 'Catalog loaded'}
        description={receivedAt ? <><span>{error || loading ? 'Last successful retrieval: ' : 'Retrieved: '}{receipt}</span><span className="stat-note">Local browser time; not a database update time.</span></> : 'Waiting for a successful catalog response.'} />
    </div>
    {error && <div className="dashboard-error error" role="alert"><strong>Catalog unavailable</strong><p>{error}</p><p>Refresh the overview to try again. Provider reporting is independent of the catalog.</p></div>}
    <section className="dashboard-section" aria-labelledby="provider-heading">
      <div className="section-heading"><h2 id="provider-heading">AI provider reporting</h2><p>Reporting availability does not indicate whether the assistant can access a provider.</p></div>
      <div className="provider-grid"><ProviderUsageCard provider="OpenAI" /><ProviderUsageCard provider="Anthropic" /></div>
    </section>
    <section className="dashboard-section" aria-labelledby="tables-heading">
      <div className="section-heading"><h2 id="tables-heading">Explore your data</h2><p>Open a table to browse its read-only records.</p></div>
      <div className="data-panel" aria-busy={loading}>
        {loading ? <div className="loading" role="status"><span className="spinner" />Loading table catalog…</div>
          : error ? <div className="empty-response"><h3>Table overview unavailable</h3><p>The catalog could not be retrieved. No current table count is available.</p></div>
          : <TableDirectory tables={tables} />}
      </div>
    </section>
  </section>;
}
