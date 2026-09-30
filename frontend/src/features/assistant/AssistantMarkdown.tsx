import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

const components: Components = {
  // Keep generated document headings below the panel's Response heading.
  h1: ({ children }) => <h4 className="markdown-heading-major">{children}</h4>,
  h2: ({ children }) => <h4>{children}</h4>,
  h3: ({ children }) => <h5>{children}</h5>,
  h4: ({ children }) => <h6>{children}</h6>,
  h5: ({ children }) => <h6>{children}</h6>,
  h6: ({ children }) => <h6>{children}</h6>,
  a: ({ href, children, title }) => href
    ? <a href={href} title={title} target="_blank" rel="noopener noreferrer">{children}<span className="sr-only"> (opens in a new tab)</span></a>
    : <span>{children}</span>,
  // Do not load model-selected remote images or tracking URLs.
  img: ({ alt }) => <span>{alt || 'Image omitted'}</span>,
  table: ({ children }) => <div className="assistant-markdown-table" role="region" aria-label="Response table, scroll horizontally for more columns" tabIndex={0}><table>{children}</table></div>,
  pre: ({ children }) => <pre tabIndex={0} aria-label="Code block, scroll horizontally for long lines">{children}</pre>,
};

export default function AssistantMarkdown({ text }: { text: string }) {
  return <div className="assistant-markdown"><Markdown remarkPlugins={[remarkGfm]} skipHtml components={components}>{text}</Markdown></div>;
}
