import type { IconName } from '../../components/Icon';
import type { TableSummary } from '../../types';

// Presentation only: the API catalog determines which links exist and their labels.
const order = ['public.payments', 'public.rides', 'public.users', 'public.vehicles', 'public.ratings'];
const icons: Record<string, IconName> = {
  'public.payments': 'payments', 'public.rides': 'rides', 'public.users': 'users',
  'public.vehicles': 'vehicles', 'public.ratings': 'ratings',
};
export const tablePath = (id: string) => `/data/${encodeURIComponent(id)}`;
export const tableIcon = (id: string): IconName => icons[id] ?? 'table';
export function navigationTables(tables: TableSummary[]) {
  const rank = (id: string) => { const index = order.indexOf(id); return index < 0 ? order.length : index; };
  return [...tables].sort((a, b) => rank(a.id) - rank(b.id) || a.label.localeCompare(b.label));
}
