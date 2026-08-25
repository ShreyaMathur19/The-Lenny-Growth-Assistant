import ReactMarkdown from "react-markdown";
import { ExternalLink } from "lucide-react";
import type { Message } from "../types";

export function MessageBubble({ message }: { message: Message }) {
  return (
    <article className={`message ${message.role}`}>
      <div className="message-label">{message.role === "user" ? "You" : "Lenny Growth Assistant"}</div>
      <div className="message-content"><ReactMarkdown>{message.content}</ReactMarkdown></div>
      {message.sources?.length > 0 && (
        <details className="sources">
          <summary>Sources ({message.sources.length})</summary>
          <div className="source-list">
            {message.sources.map((source, i) => (
              <div className="source-card" key={`${source.id}-${i}`}>
                <div className="source-title">[S{i + 1}] {source.episode_title || source.source_path}</div>
                {source.guest && <div className="source-meta">Guest: {source.guest}</div>}
                <p>{source.excerpt}</p>
                {source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer">View transcript <ExternalLink size={12} /></a>}
              </div>
            ))}
          </div>
        </details>
      )}
    </article>
  );
}
