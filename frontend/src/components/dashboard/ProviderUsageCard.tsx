// Reporting is not implemented by the current API. This does not imply that
// the provider's inference credentials are missing or that the provider is down.
export default function ProviderUsageCard({ provider }: { provider: 'OpenAI' | 'Anthropic' }) {
  return <section className="provider-card" aria-label={`${provider} usage reporting`}>
    <div className="stat-heading"><h3>{provider}</h3><span className="badge">Unavailable</span></div>
    <p className="provider-status">Usage reporting not connected</p>
    <p className="stat-description">Usage and cost data are not available in this workspace. Balance unavailable.</p>
  </section>;
}
