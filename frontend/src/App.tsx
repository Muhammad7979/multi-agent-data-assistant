import { Route, Routes, Link } from 'react-router';
import AppShell from './components/layout/AppShell';
import { TableCatalogProvider } from './features/tables/TableCatalogProvider';
import { AssistantProvider } from './features/assistant/AssistantProvider';
import AssistantRoute from './features/assistant/AssistantRoute';
import DataPage from './pages/DataPage';
import HomePage from './pages/HomePage';
import PolicyPage from './pages/PolicyPage';
import ETLFilesPage from './pages/ETLFilesPage';
import ETLFilePage from './pages/ETLFilePage';

export default function App() {
  return <AssistantProvider><TableCatalogProvider><AppShell><Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/policy" element={<PolicyPage />} />
    <Route path="/etl/files" element={<ETLFilesPage />} />
    <Route path="/etl/files/:fileId" element={<ETLFilePage />} />
    <Route path="/assistant" element={<AssistantRoute />} />
    <Route path="/data" element={<DataPage />} />
    <Route path="/data/:tableId" element={<DataPage />} />
    <Route path="*" element={<section className="page"><div className="eyebrow">Workspace</div><h1>Page not found</h1><p className="intro">This page isn't part of your workspace.</p><Link to="/">Return home</Link></section>} />
  </Routes></AppShell></TableCatalogProvider></AssistantProvider>;
}
