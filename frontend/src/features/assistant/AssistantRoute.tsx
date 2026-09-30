import { useEffect } from 'react';
import { Navigate } from 'react-router';
import { useAssistant } from './AssistantProvider';

// Preserve bookmarks to the previous assistant page without a second UI.
export default function AssistantRoute() {
  const { openAssistant } = useAssistant();
  useEffect(() => { openAssistant(); }, [openAssistant]);
  return <Navigate to="/" replace />;
}
