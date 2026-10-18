import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowRight, BookOpen, Check, ChevronRight, CircleHelp, Cpu, Download, FileCode2,
  FolderOpen, LogOut, MessageCircle, Plus, Send, Sparkles, Trash2, User, WandSparkles,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { api } from "./api";
import { useAuth } from "./auth";
import { demoMode } from "./firebase";
import type { ChatMessage, Project } from "./types";

const examples = [
  "A food delivery app for local restaurants",
  "A platform where students share notes",
  "An AI-powered resume builder",
];

function ErrorNotice({ message, onClose }: { message: string; onClose: () => void }) {
  return <div className="error-notice" role="alert"><span>{message}</span><button onClick={onClose} aria-label="Dismiss error">×</button></div>;
}

function AuthScreen() {
  const { signInEmail, signUpEmail, signInGoogle, resetPassword } = useAuth();
  const [view, setView] = useState<"signin" | "signup" | "reset">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      if (view === "signin") await signInEmail(email, password);
      else if (view === "signup") await signUpEmail(name, email, password);
      else { await resetPassword(email); setSent(true); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sign-in failed"); }
    finally { setBusy(false); }
  }

  async function google() {
    setBusy(true); setError("");
    try { await signInGoogle(); }
    catch (cause) {
      const code = cause && typeof cause === "object" && "code" in cause ? String(cause.code) : "";
      if (code === "auth/popup-blocked") {
        setError("Your browser blocked Google sign-in. Allow pop-ups for this site in the address bar, then try again.");
      } else if (code === "auth/unauthorized-domain") {
        setError("This site's domain must be added to Firebase Authentication's authorized domains.");
      } else {
        setError(cause instanceof Error ? cause.message : "Google sign-in failed");
      }
    }
    finally { setBusy(false); }
  }

  return <main className="auth-shell grid-bg">
    <div className="auth-card">
      <div className="brand brand-large"><span className="brand-icon"><Cpu size={24} /></span><span>Architect<span className="brand-accent">AI</span></span></div>
      <p className="muted">Turn an idea into a technical blueprint you can build.</p>
      <h1>{view === "signin" ? "Welcome back" : view === "signup" ? "Create your account" : "Reset password"}</h1>
      {error && <ErrorNotice message={error} onClose={() => setError("")} />}
      {sent ? <p className="success-note">If an account exists, a reset link has been sent to {email}.</p> : <>
        {view !== "reset" && <button className="button secondary full" onClick={google} disabled={busy}>Continue with Google</button>}
        <form onSubmit={submit} className="auth-form">
          {view === "signup" && <label>Full name<input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} /></label>}
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          {view !== "reset" && <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} /></label>}
          <button className="button primary full" disabled={busy}>{busy ? "Please wait…" : view === "signin" ? "Sign in" : view === "signup" ? "Create account" : "Send reset link"}<ArrowRight size={16} /></button>
        </form>
      </>}
      <div className="auth-links">
        <button onClick={() => { setView(view === "signin" ? "signup" : "signin"); setError(""); setSent(false); }}>{view === "signin" ? "Create account" : "Back to sign in"}</button>
        {view === "signin" && <button onClick={() => { setView("reset"); setError(""); }}>Forgot password?</button>}
      </div>
    </div>
  </main>;
}

export function App() {
  const { user, loading: authLoading, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [idea, setIdea] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [error, setError] = useState("");
  const [aiConfigured, setAiConfigured] = useState(true);
  const chatScroll = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) return;
    let active = true;
    api.projects().then((items) => {
      if (!active) return;
      setProjects(items);
      const savedId = localStorage.getItem("architect-ai-active-project");
      setProject(items.find((item) => item.id === savedId) || null);
    }).catch((cause) => { if (active) setError(cause.message); });
    api.health().then((health) => { if (active) setAiConfigured(health.ai_configured); }).catch(() => {});
    return () => { active = false; };
  }, [user?.uid]);

  useEffect(() => {
    if (!project) { setMessages([]); return; }
    let active = true;
    api.messages(project.id).then((items) => { if (active) setMessages(items); }).catch((cause) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [project?.id]);

  useEffect(() => {
    if (chatScroll.current) chatScroll.current.scrollTop = chatScroll.current.scrollHeight;
  }, [messages]);

  function select(item: Project | null) {
    setProject(item);
    if (item) localStorage.setItem("architect-ai-active-project", item.id);
    else localStorage.removeItem("architect-ai-active-project");
  }

  function apply(item: Project) {
    setProject(item);
    localStorage.setItem("architect-ai-active-project", item.id);
    setProjects((current) => [item, ...current.filter((other) => other.id !== item.id)]);
  }

  async function work(label: string, task: () => Promise<void>) {
    setBusy(label); setError("");
    try { await task(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Something went wrong"); }
    finally { setBusy(""); }
  }

  function create(event: FormEvent) {
    event.preventDefault();
    if (idea.trim().length < 10) { setError("Describe your idea in at least 10 characters."); return; }
    void work("create", async () => { const item = await api.create(idea.trim()); apply(item); setIdea(""); });
  }

  function answer(questionId: string, selection: string) {
    if (!project) return;
    void work("answer", async () => apply(await api.answer(project.id, questionId, selection)));
  }

  function addCategory(event: FormEvent) {
    event.preventDefault();
    if (!project || !newCategory.trim()) return;
    void work("category", async () => { apply(await api.category(project.id, newCategory.trim())); setNewCategory(""); });
  }

  function generateGuide() {
    if (!project) return;
    void work("guide", async () => apply(await api.guide(project.id)));
  }

  function rename(item: Project) {
    const name = window.prompt("Project name", item.name)?.trim();
    if (!name || name === item.name) return;
    void work("rename", async () => apply(await api.rename(item.id, name)));
  }

  function remove(item: Project) {
    if (!window.confirm(`Delete "${item.name}" and its chat history?`)) return;
    void work("delete", async () => {
      await api.delete(item.id);
      setProjects((current) => current.filter((other) => other.id !== item.id));
      if (project?.id === item.id) select(null);
    });
  }

  async function sendChat(event: FormEvent) {
    event.preventDefault();
    if (!project || !chatInput.trim() || chatBusy) return;
    const text = chatInput.trim();
    setChatInput(""); setChatBusy(true); setError("");
    const userMessage: ChatMessage = { id: `pending-user-${Date.now()}`, role: "user", content: text, created_at: new Date().toISOString() };
    const assistantId = `pending-assistant-${Date.now()}`;
    setMessages((current) => [...current, userMessage, { id: assistantId, role: "assistant", content: "", created_at: new Date().toISOString() }]);
    try {
      await api.streamChat(project.id, text, (delta) => {
        setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: item.content + delta } : item));
      });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Chat failed"); }
    finally {
      try { setMessages(await api.messages(project.id)); } catch { /* Keep visible stream on a read failure. */ }
      setChatBusy(false);
    }
  }

  function clearChat() {
    if (!project || !window.confirm("Clear this project's chat history?")) return;
    void work("clear-chat", async () => { await api.clearMessages(project.id); setMessages([]); });
  }

  if (authLoading) return <div className="center-screen">Loading your account…</div>;
  if (!user) return <AuthScreen />;
  const question = project?.phase === "deciding" ? project.questions[project.current_index] : undefined;
  const progress = project ? (project.questions.length ? Math.min(100, Math.round(project.current_index / project.questions.length * 100)) : 100) : 0;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-icon"><Cpu size={20} /></span><span>Architect<span className="brand-accent">AI</span></span></div>
      <p className="sidebar-subtitle">From idea to blueprint</p>
      <button className="button primary full new-button" onClick={() => select(null)}><Plus size={17} /> New blueprint</button>
      <div className="sidebar-heading"><FolderOpen size={15} /> Saved projects <span>{projects.length}</span></div>
      <nav className="project-list" aria-label="Saved projects">
        {projects.length === 0 && <p className="sidebar-empty">Your blueprints will appear here.</p>}
        {projects.map((item) => <div className={`project-row ${project?.id === item.id ? "active" : ""}`} key={item.id}>
          <button className="project-select" onClick={() => select(item)}><FileCode2 size={15} /><span>{item.name}</span></button>
          <button className="icon-button project-action" onClick={() => rename(item)} aria-label={`Rename ${item.name}`}>✎</button>
          <button className="icon-button project-action" onClick={() => remove(item)} aria-label={`Delete ${item.name}`}><Trash2 size={13} /></button>
        </div>)}
      </nav>
      <div className="sidebar-footer"><span className="avatar"><User size={16} /></span><div><strong>{user.displayName || user.email || "Demo User"}</strong><small>{demoMode ? "Local demo" : "Firebase account"}</small></div>{!demoMode && <button className="icon-button" onClick={() => void logout()} title="Sign out"><LogOut size={17} /></button>}</div>
    </aside>

    <main className="workspace grid-bg">
      <header className="topbar"><div className="topbar-title"><Cpu size={18} /><strong>{project ? project.name : "New blueprint"}</strong></div><span className={`mode-pill ${!aiConfigured ? "demo-pill" : ""}`}>{aiConfigured ? "AI configured" : demoMode ? "Demo AI" : "AI setup needed"}</span></header>
      {error && <ErrorNotice message={error} onClose={() => setError("")} />}
      {!aiConfigured && <div className="demo-banner"><CircleHelp size={16} /> {demoMode ? "Local demo is using example AI output." : "AI is unavailable."} Add an OpenAI key on the backend for personalized questions and guides.</div>}

      {!project ? <section className="welcome-panel">
        <div className="welcome-icon"><Sparkles size={27} /></div>
        <p className="eyebrow">YOUR IDEA, ENGINEERED</p>
        <h1>Turn a startup idea into a <span>buildable blueprint.</span></h1>
        <p className="lead">Answer a few practical questions. Get a clear architecture, implementation guide, and an assistant that remembers your project.</p>
        <form onSubmit={create} className="idea-form">
          <textarea value={idea} onChange={(event) => setIdea(event.target.value)} placeholder="Describe your startup idea…" maxLength={3000} />
          <div className="idea-form-footer"><small>Be specific about who will use it and what it does.</small><button className="button primary" disabled={!!busy || idea.trim().length < 10}>{busy === "create" ? "Planning…" : "Build blueprint"}<ArrowRight size={17} /></button></div>
        </form>
        <div className="examples"><span>Try an example</span>{examples.map((sample) => <button key={sample} onClick={() => setIdea(sample)}>{sample}<ChevronRight size={14} /></button>)}</div>
      </section> : <div className="workspace-columns">
        <section className="decision-column">
          <div className="section-heading"><div><p className="eyebrow">PROJECT WORKSPACE</p><h1>{project.phase === "complete" ? "Your architecture is ready" : "Make the key decisions"}</h1></div><span className="progress-count">{project.current_index}/{project.questions.length}</span></div>
          <p className="project-idea">{project.idea}</p>
          <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
          {question ? <div className="question-card" key={question.id}>
            <span className="category-pill">{question.category}</span>
            <h2>{question.question}</h2>
            <p className="muted">Choose the option that fits your first release. You can also write your own answer.</p>
            <div className="options">{question.options.map((option) => <button key={option.label} disabled={!!busy} onClick={() => answer(question.id, option.label)}><strong>{option.label}</strong><small>{option.description}</small><ChevronRight size={18} /></button>)}</div>
            <form className="custom-answer" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const input = form.elements.namedItem("custom") as HTMLInputElement; if (input.value.trim()) answer(question.id, input.value.trim()); }}><input name="custom" placeholder="Or enter your own choice" maxLength={200} disabled={!!busy} /><button className="button secondary" disabled={!!busy}>Use answer</button></form>
          </div> : <div className="complete-card"><span className="complete-icon"><Check size={25} /></span><h2>Decisions saved</h2><p>You've answered the architecture questions. Generate the implementation guide when you're ready.</p><button className="button primary" onClick={generateGuide} disabled={!!busy || !!project.guide}><WandSparkles size={17} />{project.guide ? "Guide generated" : busy === "guide" ? "Generating…" : "Generate guide"}</button></div>}
          {!project.guide && <form className="add-category" onSubmit={addCategory}><label htmlFor="category">Need another decision category?</label><div><input id="category" value={newCategory} onChange={(event) => setNewCategory(event.target.value)} placeholder="e.g. Payments" maxLength={60} /><button className="button secondary" disabled={!!busy || newCategory.trim().length < 2}><Plus size={16} /> Add</button></div></form>}
          <section className="chat-section"><div className="chat-heading"><div><MessageCircle size={18} /><h2>Ask the AI architect</h2></div>{messages.length > 0 && <button className="subtle-button" onClick={clearChat}>Clear chat</button>}</div><p className="muted">The assistant sees this project's decisions and recent messages.</p>
            <div className="chat-messages" ref={chatScroll}>{messages.length === 0 && <div className="chat-empty">Ask how to build, deploy, or improve your architecture.</div>}{messages.map((item) => <div key={item.id} className={`chat-bubble ${item.role}`}><span>{item.role === "user" ? "You" : "Architect AI"}</span><div className="markdown"><ReactMarkdown>{item.content || "Thinking…"}</ReactMarkdown></div></div>)}</div>
            <form className="chat-form" onSubmit={(event) => void sendChat(event)}><input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask about this architecture…" disabled={chatBusy} /><button className="button primary" disabled={chatBusy || !chatInput.trim()} aria-label="Send message"><Send size={17} /></button></form>
          </section>
        </section>
        <aside className="blueprint-column"><div className="blueprint-header"><div><FileCode2 size={18} /><strong>Architecture blueprint</strong></div><div className="export-buttons"><button onClick={() => void api.download(project.id, "md").catch((cause) => setError(cause.message))} title="Download Markdown"><Download size={15} /> MD</button><button onClick={() => void api.download(project.id, "pdf").catch((cause) => setError(cause.message))} title="Download PDF"><Download size={15} /> PDF</button></div></div>
          <div className="blueprint-content"><div className="blueprint-intro"><p className="eyebrow">THE PLAN SO FAR</p><h2>{project.name}</h2><p>{project.idea}</p></div>
            <h3>Decisions</h3>{project.architecture.length === 0 && <p className="muted">Your choices will appear here.</p>}{project.architecture.map((entry, index) => <div className="decision-card" key={`${entry.category}-${index}`}><span>{entry.category}</span><strong>{entry.selection}</strong></div>)}
            {project.guide && <div className="guide-content"><h3><BookOpen size={17} /> Implementation guide</h3><h4>Project structure</h4><div className="code-list">{project.guide.projectStructure.map((line) => <div key={line}>{line}</div>)}</div><h4>Build steps</h4>{project.guide.implementationSteps.map((step) => <div className="step-row" key={step.step}><span>{step.step}</span><div><strong>{step.title}</strong><p>{step.description}</p></div></div>)}<h4>Deployment</h4><ul>{project.guide.deploymentSteps.map((step) => <li key={step}>{step}</li>)}</ul><h4>Environment variables</h4><div className="code-list">{project.guide.envVars.map((item) => <div key={item}>{item}</div>)}</div></div>}
          </div>
        </aside>
      </div>}
    </main>
  </div>;
}
