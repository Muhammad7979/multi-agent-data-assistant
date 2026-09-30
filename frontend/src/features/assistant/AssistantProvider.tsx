import { createContext, useCallback, useContext, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { askAssistant } from '../../api';
import type { AssistantResponse } from '../../types';

type AssistantState = {
  filesRevision: number;
  open: boolean; openAssistant: () => void; closeAssistant: () => void;
  question: string; setQuestion: (value: string) => void; submittedQuestion: string;
  response: AssistantResponse | null; error: string; loading: boolean; submit: () => Promise<void>;
};
const AssistantContext = createContext<AssistantState | null>(null);

export function AssistantProvider({ children }: { children: ReactNode }) {
  // In-memory, per-tab state: navigation and dismissal preserve it; reload resets it.
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [submittedQuestion, setSubmittedQuestion] = useState('');
  const [response, setResponse] = useState<AssistantResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [filesRevision, setFilesRevision] = useState(0);
  const inFlight = useRef(false);
  const openAssistant = useCallback(() => setOpen(true), []);
  const closeAssistant = useCallback(() => setOpen(false), []);

  async function submit() {
    if (inFlight.current || !question.trim() || question.length > 5000) return;
    inFlight.current = true;
    setLoading(true); setError(''); setResponse(null); setSubmittedQuestion(question);
    try {
      const result = await askAssistant(question);
      setResponse(result);
      if (result.route === 'etl' && result.files?.length) setFilesRevision(value => value + 1);
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'The request failed.'); }
    finally { inFlight.current = false; setLoading(false); }
  }

  return <AssistantContext.Provider value={{ filesRevision, open, openAssistant, closeAssistant, question, setQuestion, submittedQuestion, response, error, loading, submit }}>
    {children}
  </AssistantContext.Provider>;
}

export function useAssistant() {
  const state = useContext(AssistantContext);
  if (!state) throw new Error('Assistant must be used inside its provider.');
  return state;
}
