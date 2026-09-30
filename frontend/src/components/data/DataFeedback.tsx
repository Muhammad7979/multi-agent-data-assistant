import type { ReactNode } from 'react';

export function DataLoading({ children }: { children: ReactNode }) {
  return <div className="loading" role="status"><span className="spinner" />{children}</div>;
}
export function DataError({ title, message, retry }: { title: string; message: string; retry: () => void }) {
  return <div className="error" role="alert"><strong>{title}</strong><p>{message}</p><button className="secondary" onClick={retry}>Try again</button></div>;
}
export function DataEmpty({ title, children, level = 3 }: { title: string; children: ReactNode; level?: 2 | 3 }) {
  const Heading = level === 2 ? 'h2' : 'h3';
  return <div className="empty-response"><Heading>{title}</Heading>{children}</div>;
}
