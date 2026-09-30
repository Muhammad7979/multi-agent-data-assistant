export type IconName = 'home' | 'table' | 'payments' | 'rides' | 'users' | 'vehicles' | 'ratings' | 'menu' | 'close' | 'assistant' | 'policy' | 'files';

const paths: Record<IconName, string> = {
  files: 'M3 7V4h6l3 3h9v13H3ZM12 10v7m-3-3 3 3 3-3',
  policy: 'M5 3h10l4 4v14H5ZM14 3v5h5M8 12h8M8 16h6',
  assistant: 'M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-8l-6 3v-3a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM8 9h8M8 13h5',
  home: 'm3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  table: 'M4 4h16v16H4ZM4 9h16M9 9v11',
  payments: 'M3 5h18v14H3ZM3 10h18M7 15h3',
  rides: 'M5 5h.01M19 19h.01M8 5h7a4 4 0 0 1 0 8H9a3 3 0 0 0 0 6h7M7 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0ZM21 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  vehicles: 'm5 7 2-4h10l2 4M3 11l2-4h14l2 4v7H3ZM5 18v3M19 18v3M6 13h2M16 13h2',
  ratings: 'm12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z',
  menu: 'M4 6h16M4 12h16M4 18h16',
  close: 'm6 6 12 12M6 18 18 6',
};

export default function Icon({ name }: { name: IconName }) {
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
