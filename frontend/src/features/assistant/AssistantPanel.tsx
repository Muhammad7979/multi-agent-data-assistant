import { useEffect, useRef } from 'react';
import Icon from '../../components/Icon';
import { trapDialogFocus } from '../../components/layout/dialogFocus';
import { useAssistant } from './AssistantProvider';
import AssistantMarkdown from './AssistantMarkdown';
import { Link } from 'react-router';
import ETLDownload from '../etl/ETLDownload';

const examples = ['How many users are registered?', 'Show the five most recent rides.', 'What is the average rating?'];

export default function AssistantPanel() {
  const { open, closeAssistant, question, setQuestion, submittedQuestion, response, error, loading, submit } = useAssistant();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open) {
      returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      element.showModal();
      // A pending question is disabled; keep the close control focused in that case.
      if (!input.current?.disabled) input.current?.focus({ preventScroll: true });
      const previous = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = previous; element.close(); };
    }
  }, [open]);

  useEffect(() => { if (loading && content.current) content.current.scrollTop = 0; }, [loading]);

  return <dialog ref={dialog} id="assistant-panel" className="assistant-dialog" aria-labelledby="assistant-title"
    onKeyDown={trapDialogFocus}
    onCancel={event => { event.preventDefault(); closeAssistant(); }}
    onClose={() => {
      // A queued close event must not dismiss a panel that was already reopened.
      if (dialog.current?.open) return;
      closeAssistant();
      const target = returnFocus.current;
      if (target?.isConnected && target !== document.body) target.focus({ preventScroll: true });
      else document.getElementById('assistant-launcher')?.focus({ preventScroll: true });
    }}
    onClick={event => {
      if (event.target !== event.currentTarget) return;
      const rect = event.currentTarget.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeAssistant();
    }}>
    <div className="assistant-panel-inner">
      <header className="assistant-header"><span className="assistant-identity"><Icon name="assistant" /></span><div><h2 id="assistant-title">Data Agent</h2><p>Your data assistant</p></div>
        <button className="icon-button" aria-label="Close assistant" onClick={closeAssistant}><Icon name="close" /></button>
      </header>
      <div ref={content} className="assistant-content" tabIndex={0} role="region" aria-label="Assistant content">
        <p className="assistant-scope">Each question stands alone. The current table does not limit the assistant’s scope.</p>
        {!submittedQuestion ? <div className="assistant-welcome"><h3>What would you like to explore?</h3><p>Ask about your database, company policies, or describe an ETL operation.</p>
          <div className="assistant-examples">{examples.map(example => <button key={example} className="secondary" onClick={() => { setQuestion(example); input.current?.focus(); }}>{example}<span aria-hidden="true">↗</span></button>)}</div>
        </div> : <>
          <div className="assistant-question"><h3>Your question</h3><p>{submittedQuestion}</p></div>
          <section aria-labelledby="assistant-response-title" aria-busy={loading}>
            <div className="assistant-response-heading"><h3 id="assistant-response-title">Response</h3>{response && <div className="badges"><span className="badge">{response.route.toUpperCase()}</span><span className={`badge ${response.status !== 'answered' ? 'warning' : ''}`}>{response.status === 'declined' ? 'Declined' : response.status === 'insufficient_evidence' ? 'Insufficient evidence' : 'Answer received'}</span></div>}</div>
            {loading ? <div className="assistant-progress" role="status"><span className="spinner" /><p>Working on your request. You can close this panel while it runs.</p></div>
              : error ? <div className="error" role="alert"><strong>Request unavailable</strong><p>{error}</p><p>Backend work may still be running. Requests are not retried automatically; check before submitting the same ETL operation again.</p></div>
              : response ? <div aria-live="polite">
                {response.route === 'etl' && !response.files && <div className="assistant-etl notice"><strong>Experimental ETL response</strong><p>This is the agent’s report, not verified completion. Confirm files and outcomes yourself. Closing the panel does not stop backend work or roll back changes.</p></div>}
                <AssistantMarkdown text={response.answer} />
                {!!response.files?.length && <section className="assistant-sources" aria-label="Saved ETL files">
                  <h4>Saved files</h4><ul>{response.files.map(file => <li key={file.id}>
                    <span>{file.filename}</span>{' · '}
                    <div className="etl-actions"><Link to={`/etl/files/${encodeURIComponent(file.id)}`} onClick={closeAssistant} aria-label={`Open ${file.filename}`}>Open</Link>
                      <ETLDownload id={file.id} filename={file.filename} /></div>
                  </li>)}</ul>
                </section>}
                {response.route === 'policy' && !!response.sources?.length && <section className="assistant-sources" aria-label="Policy sources">
                  <h4>Sources</h4><ul>{response.sources.map(source => <li key={source.source_id}>
                    [{source.source_id}] {source.filename}{source.page !== null && ` · Page ${source.page}`}{source.section && ` · ${source.section}`}
                  </li>)}</ul>
                </section>}
              </div> : null}
          </section>
        </>}
      </div>
      <form className="assistant-composer" onSubmit={event => { event.preventDefault(); void submit(); }}>
        <label htmlFor="assistant-question">Ask a question</label>
        <textarea ref={input} id="assistant-question" value={question} maxLength={5000} rows={3} disabled={loading}
          onChange={event => setQuestion(event.target.value)} placeholder="What would you like to know?" aria-describedby="assistant-request-hint assistant-character-count"
          onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(); } }} />
        <div className="composer-bottom"><span id="assistant-character-count">{question.length.toLocaleString()} / 5,000</span><button type="submit" className="primary" disabled={loading || !question.trim() || question.length > 5000}>{loading ? 'Working…' : 'Send question'}<span aria-hidden="true">↗</span></button></div>
        <p id="assistant-request-hint" className="assistant-request-hint">ETL is experimental and may write files or execute code. Use trusted development data only. Ctrl/⌘ + Enter to send.</p>
      </form>
    </div>
  </dialog>;
}
