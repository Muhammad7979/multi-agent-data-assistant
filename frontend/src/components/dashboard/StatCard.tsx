import type { ReactNode } from 'react';
import Icon from '../Icon';
import type { IconName } from '../Icon';

type Props = { title: string; icon: IconName; value: ReactNode; description: ReactNode; loading?: boolean; unavailable?: boolean };

export default function StatCard({ title, icon, value, description, loading = false, unavailable = false }: Props) {
  return <section className="stat-card" aria-label={title} aria-busy={loading}>
    <div className="stat-heading"><h2>{title}</h2><Icon name={icon} /></div>
    <div className={`stat-value${unavailable ? ' stat-unavailable' : ''}`}>
      {loading ? <span className="stat-loading" role="status"><span className="spinner" />Loading</span> : value}
    </div>
    <div className="stat-description">{description}</div>
  </section>;
}
