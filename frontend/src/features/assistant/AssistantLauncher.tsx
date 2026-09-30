import Icon from '../../components/Icon';
import { useAssistant } from './AssistantProvider';

export default function AssistantLauncher() {
  const { open, openAssistant, loading } = useAssistant();
  return <div className="assistant-dock"><button id="assistant-launcher" className="assistant-launcher" onClick={openAssistant}
    aria-label={loading ? 'Open Data Agent assistant, request in progress' : 'Open Data Agent assistant'}
    aria-haspopup="dialog" aria-expanded={open} aria-controls="assistant-panel">
    {loading ? <span className="spinner" /> : <Icon name="assistant" />}<span>Ask Data Agent</span>
  </button></div>;
}
