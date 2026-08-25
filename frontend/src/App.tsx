import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, FileText, Menu, Plus, Send, Sparkles } from "lucide-react";
import { api } from "./api";
import { ArtifactViewer } from "./components/ArtifactViewer";
import { MessageBubble } from "./components/MessageBubble";
import type { Artifact, Message, Session } from "./types";
import "./styles.css";

const WELCOME: Message = {
  id: "welcome",
  role: "assistant",
  content: "Ask a product or growth question grounded in Lenny's Podcast transcripts. I can also turn the research into a **Ship 30 for 30 essay** or a rendered **Markdown/HTML artifact**.",
  sources: [],
  created_at: new Date().toISOString()
};

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState<"ollama" | "cloud">("ollama");
  const [mode, setMode] = useState<"auto" | "qa" | "ship30" | "artifact">("auto");
  const [artifactType, setArtifactType] = useState<"markdown" | "html">("markdown");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { void loadSessions(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  async function loadSessions() {
    try { setSessions(await api.listSessions()); } catch { /* first start may be before API is ready */ }
  }

  async function newChat() {
    setError(null);
    try {
      const session = await api.createSession();
      setSessionId(session.id);
      setMessages([WELCOME]);
      setArtifact(null);
      await loadSessions();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create chat"); }
  }

  async function openSession(id: string) {
    setSessionId(id);
    setArtifact(null);
    setError(null);
    try {
      const [history, artifacts] = await Promise.all([api.listMessages(id), api.listArtifacts(id)]);
      setMessages(history.length ? history : [WELCOME]);
      setArtifact(artifacts[0] ?? null);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load chat"); }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    setInput("");
    let sid = sessionId;
    try {
      if (!sid) {
        const session = await api.createSession();
        sid = session.id;
        setSessionId(sid);
      }
      const optimistic: Message = { id: `tmp-${Date.now()}`, role: "user", content: text, sources: [], created_at: new Date().toISOString() };
      setMessages((m) => [...m.filter((x) => x.id !== "welcome"), optimistic]);
      const result = await api.chat({ session_id: sid, message: text, provider, mode, artifact_type: artifactType });
      setMessages((m) => [...m, result.message]);
      if (result.artifact) setArtifact(result.artifact);
      await loadSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally { setLoading(false); }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="brand"><div className="brand-mark"><Bot size={20} /></div><span>Lenny Growth</span></div>
        <button className="new-chat" onClick={newChat}><Plus size={17} /> New chat</button>
        <div className="session-list" aria-label="Previous chats">
          {sessions.map((s) => <button key={s.id} className={s.id === sessionId ? "session active" : "session"} onClick={() => openSession(s.id)}>{s.title}</button>)}
        </div>
        <div className="sidebar-footer">Grounded in Lenny's Podcast transcripts</div>
      </aside>

      <main className="main-column">
        <header className="topbar">
          <button className="icon-button" onClick={() => setSidebarOpen((v) => !v)} aria-label="Toggle sidebar"><Menu size={19} /></button>
          <div className="title-block"><strong>The Lenny Growth Assistant</strong><span>Product & growth research, grounded in transcripts</span></div>
          <div className="toolbar">
            <label><span>Model</span><select value={provider} onChange={(e) => setProvider(e.target.value as "ollama" | "cloud")}><option value="ollama">Ollama · Local</option><option value="cloud">Cloud</option></select></label>
            <label><span>Mode</span><select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}><option value="auto">Auto</option><option value="qa">Q&A</option><option value="ship30">Ship 30</option><option value="artifact">Artifact</option></select></label>
          </div>
        </header>

        <div className={artifact ? "workspace with-artifact" : "workspace"}>
          <section className="chat-column">
            <div className="messages">
              {messages.map((m) => <MessageBubble key={m.id} message={m} />)}
              {loading && <div className="thinking"><Sparkles size={16} /> Retrieving transcripts and generating a grounded answer…</div>}
              {error && <div className="error-banner">{error}</div>}
              <div ref={endRef} />
            </div>

            <div className="composer-wrap">
              <div className="quick-actions">
                <button onClick={() => setInput("What are the best lessons from Lenny's guests for improving product activation?")}>Activation strategy</button>
                <button onClick={() => { setMode("ship30"); setInput("Write a Ship 30 for 30 essay about product retention using the transcript evidence."); }}><FileText size={13} /> Ship 30 essay</button>
                <button onClick={() => { setMode("artifact"); setArtifactType("html"); setInput("Create an HTML executive brief summarizing the strongest growth lessons from this conversation."); }}>HTML artifact</button>
              </div>
              <form className="composer" onSubmit={submit}>
                <textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about product, growth, onboarding, retention…" rows={3} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
                <div className="composer-footer">
                  <div className="artifact-type">Artifact: <select value={artifactType} onChange={(e) => setArtifactType(e.target.value as "markdown" | "html")}><option value="markdown">Markdown</option><option value="html">HTML</option></select></div>
                  <button className="send" disabled={loading || !input.trim()}><Send size={16} /> Send</button>
                </div>
              </form>
              <p className="disclaimer">Answers are constrained to indexed transcript evidence. Verify important decisions against the cited source.</p>
            </div>
          </section>
          <ArtifactViewer artifact={artifact} onClose={() => setArtifact(null)} />
        </div>
      </main>
    </div>
  );
}
