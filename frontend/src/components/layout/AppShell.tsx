import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router';
import Sidebar, { Brand } from './Sidebar';
import Icon from '../Icon';
import AssistantLauncher from '../../features/assistant/AssistantLauncher';
import AssistantPanel from '../../features/assistant/AssistantPanel';
import { trapDialogFocus } from './dialogFocus';

export default function AppShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const location = useLocation();

  useEffect(() => { setMenuOpen(false); }, [location.pathname, location.search]);
  useEffect(() => {
    const mobile = window.matchMedia('(max-width: 767px)');
    const closeOnDesktop = () => { if (!mobile.matches) setMenuOpen(false); };
    mobile.addEventListener('change', closeOnDesktop);
    return () => mobile.removeEventListener('change', closeOnDesktop);
  }, []);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (menuOpen) {
      element.showModal();
      const previous = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = previous; element.close(); };
    }
    if (element.open) element.close();
  }, [menuOpen]);

  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="desktop-sidebar"><Sidebar /></aside>
    <header className="mobile-header"><Brand /><button ref={menuButton} className="icon-button" aria-label="Open navigation"
      aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(true)}><Icon name="menu" /></button></header>
    <dialog ref={dialog} id="mobile-navigation" className="mobile-navigation" aria-label="Navigation"
      onKeyDown={trapDialogFocus}
      onCancel={() => setMenuOpen(false)} onClose={() => { if (dialog.current?.open) return; setMenuOpen(false); if (window.matchMedia('(max-width: 767px)').matches) menuButton.current?.focus(); }}
      onClick={event => { if (event.target === event.currentTarget) setMenuOpen(false); }}>
      <div className="mobile-sidebar"><button autoFocus className="icon-button navigation-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><Icon name="close" /></button>
        <Sidebar onNavigate={() => setMenuOpen(false)} />
      </div>
    </dialog>
    <div className="main-column"><div className="workspace-bar"><span>Workspace</span><span className="workspace-caption">Explore & understand your data</span></div>
      <main id="main" tabIndex={-1}>{children}</main>
    </div>
    <AssistantLauncher />
    <AssistantPanel />
  </div>;
}
