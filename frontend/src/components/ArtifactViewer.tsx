import DOMPurify from "dompurify";
import ReactMarkdown from "react-markdown";
import { FileCode2, ShieldCheck, X } from "lucide-react";
import type { Artifact } from "../types";

type Props = { artifact: Artifact | null; onClose: () => void };

export function ArtifactViewer({ artifact, onClose }: Props) {
  if (!artifact) return null;

  const sanitized = artifact.type === "html"
    ? DOMPurify.sanitize(artifact.content, {
        FORBID_TAGS: ["script", "iframe", "object", "embed", "form", "base"],
        FORBID_ATTR: ["onerror", "onload", "onclick", "onmouseover", "formaction"],
        ALLOW_UNKNOWN_PROTOCOLS: false
      })
    : "";

  return (
    <aside className="artifact-panel" aria-label="Artifact viewer">
      <div className="artifact-header">
        <div>
          <div className="artifact-kicker"><FileCode2 size={14} /> Artifact</div>
          <strong>{artifact.title}</strong>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close artifact"><X size={18} /></button>
      </div>
      <div className="security-note"><ShieldCheck size={14} /> HTML is sanitized and rendered without script permissions.</div>
      <div className="artifact-body">
        {artifact.type === "markdown" ? (
          <div className="markdown"><ReactMarkdown>{artifact.content}</ReactMarkdown></div>
        ) : (
          <iframe
            title={artifact.title}
            sandbox=""
            referrerPolicy="no-referrer"
            srcDoc={sanitized}
            className="artifact-frame"
          />
        )}
      </div>
    </aside>
  );
}
