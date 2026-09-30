import { useEffect, useRef, type ReactNode } from 'react';
import Icon from '../../components/Icon';
import { trapDialogFocus } from '../../components/layout/dialogFocus';

export default function PolicyDialog({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const target = document.activeElement as HTMLElement | null;
    const element = dialog.current!;
    const overflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = 'hidden';
    return () => { element.close(); document.body.style.overflow = overflow; if (target?.isConnected) target.focus(); };
  }, []);
  return <dialog ref={dialog} className="policy-dialog" aria-labelledby="policy-dialog-title" onKeyDown={trapDialogFocus}
    onCancel={event => { event.preventDefault(); close(); }}>
    <header><h2 id="policy-dialog-title">{title}</h2><button className="icon-button" aria-label="Close document dialog" onClick={close}><Icon name="close" /></button></header>
    {children}
  </dialog>;
}
