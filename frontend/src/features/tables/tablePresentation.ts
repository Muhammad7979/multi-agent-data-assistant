const descriptions: Record<string, string> = {
  'public.payments': 'Review ride payments, transaction references, methods and payment status.',
  'public.rides': 'Explore ride requests, trip details, fares and ride status.',
  'public.users': 'Browse rider and driver profiles, contact details and active status.',
  'public.vehicles': 'Review driver vehicles, registration details and active status.',
  'public.ratings': 'Explore ride ratings and feedback from riders.',
};
export const tableDescription = (id: string) => descriptions[id] ?? 'Browse the records available for this table.';
export const columnLabel = (name: string) => name.split('_').map(word =>
  word.toLowerCase() === 'id' ? 'ID' : word.toLowerCase() === 'km' ? 'km' : word.charAt(0).toUpperCase() + word.slice(1),
).join(' ');
