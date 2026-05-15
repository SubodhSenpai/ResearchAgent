'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { startResearch, streamResearch, interruptResearch, getUserSessions, deleteSession, getResearchSession, getSessionHistory } from '@/lib/api';
import Sidebar from './Sidebar';
import AgentPipeline from './AgentPipeline';
import ResearchResult from './ResearchResult';
import DocumentManager from './DocumentManager';

const AGENT_COLORS = {
  memory_check: '#ec4899',
  supervisor: '#f59e0b',
  researcher: '#3b82f6',
  analyst: '#8b5cf6',
  critic: '#ef4444',
  writer: '#10b981',
  save_memory: '#ec4899',
  interrupt_check: '#f59e0b',
};

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [query, setQuery] = useState('');
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [steps, setSteps] = useState([]);
  const [result, setResult] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [isResearching, setIsResearching] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // session_id pending deletion
  const [documentsModalOpen, setDocumentsModalOpen] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const abortRef = useRef(null);
  const inputRef = useRef(null);

  const loadSessions = useCallback(async () => {
    if (!user) return;
    setLoadingSessions(true);
    try {
      const data = await getUserSessions(user.user_id);
      setSessions(data.sessions || []);
    } catch { /* silently fail */ }
    setLoadingSessions(false);
  }, [user]);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const handleStartResearch = async (e) => {
    e?.preventDefault();
    if (!query.trim() || isResearching) return;
    setError(''); setSteps([]); setResult(null); setIsResearching(true);

    const activeQuery = query.trim();
    let sessionId = activeSession?.session_id;

    try {
      if (!sessionId) {
        const session = await startResearch(activeQuery, webSearchEnabled);
        sessionId = session.session_id;
        setActiveSession({ session_id: sessionId, query: activeQuery, status: 'running', created_at: session.created_at });
      } else {
        // If it's an existing session, we push the new query into the chat history immediately
        setChatHistory(prev => [...prev, { type: 'user', content: activeQuery }]);
        setQuery('');
      }

      const controller = streamResearch(
        sessionId,
        activeQuery,
        webSearchEnabled,
        (step) => setSteps((prev) => [...prev, { ...step, color: AGENT_COLORS[step.node] || '#6366f1' }]),
        (res) => {
          setResult(res);
          setIsResearching(false);
          setActiveSession((prev) => prev ? { ...prev, status: 'completed', final_answer: res.answer, quality_score: res.quality_score } : prev);
          
          // Refresh the full chat history once the run is complete
          getSessionHistory(sessionId).then(data => {
            if (data?.messages) setChatHistory(data.messages);
          }).catch(() => {});
          
          loadSessions();
          
          // Hide pipeline gracefully after completion
          setTimeout(() => setSteps([]), 1500);
        },
        (err) => { setError(err); setIsResearching(false); }
      );
      abortRef.current = controller;
    } catch (err) {
      setError(err.message);
      setIsResearching(false);
    }
  };

  const handleInterrupt = async () => {
    if (!activeSession) return;
    try {
      await interruptResearch(activeSession.session_id);
      if (abortRef.current) abortRef.current.abort();
      setIsResearching(false);
    } catch (err) { setError(err.message); }
  };

  const handleSelectSession = async (session) => {
    if (isResearching) return;
    setError(''); setSteps([]); setResult(null); setChatHistory([]);
    try {
      const data = await getResearchSession(session.session_id);
      setActiveSession(data);
      
      const historyData = await getSessionHistory(session.session_id);
      if (historyData?.messages) {
        setChatHistory(historyData.messages);
      }
      
      setQuery(''); // Reset query input so they can type follow-up
      if (data.final_answer) {
        setResult({ answer: data.final_answer, quality_score: data.quality_score, messages: [], interrupted: false });
      }
    } catch (err) { setError(err.message); }
  };

  const handleDeleteSession = (sessionId) => {
    setDeleteConfirm(sessionId);
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;
    try {
      await deleteSession(deleteConfirm);
      setSessions((prev) => prev.filter((s) => s.session_id !== deleteConfirm));
      if (activeSession?.session_id === deleteConfirm) {
        setActiveSession(null); setResult(null); setSteps([]); setQuery('');
      }
    } catch (err) { setError(err.message); }
    setDeleteConfirm(null);
  };

  const handleNewResearch = () => {
    if (isResearching) return;
    setActiveSession(null); setSteps([]); setResult(null); setChatHistory([]); setQuery(''); setError('');
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  return (
    <div className="flex h-screen overflow-hidden relative z-1">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions} activeSessionId={activeSession?.session_id}
        onSelect={handleSelectSession} onDelete={handleDeleteSession}
        onNewResearch={handleNewResearch} isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)} loading={loadingSessions}
        user={user} onLogout={logout}
        onOpenDocuments={() => setDocumentsModalOpen(true)}
      />

      {/* Main */}
      <main className={`flex-1 flex flex-col h-screen overflow-hidden transition-[margin-left] duration-250 ease-in-out ${sidebarOpen ? 'ml-[300px]' : 'ml-0'}`}>
        {/* Top bar */}
        <header className="flex items-center px-6 py-3 border-b border-border-subtle bg-bg-primary/80 backdrop-blur-[12px] min-h-[56px] gap-3 flex-shrink-0">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar" className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-glass-hover transition-all cursor-pointer">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
          <div className="flex-1 flex items-center justify-center">
            {activeSession ? (
              <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full border ${
                activeSession.status === 'completed' ? 'bg-success-bg text-success border-success/20'
                : activeSession.status === 'running' ? 'bg-warning-bg text-warning border-warning/20'
                : 'bg-info-bg text-info border-info/20'
              }`}>
                {activeSession.status}
              </span>
            ) : (
              <span className="text-xs text-text-muted">New Research</span>
            )}
          </div>
          <span className="text-xs text-text-muted">{user?.username}</span>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-12 py-8 pb-30 max-md:px-4 max-md:pb-24">
          {/* Empty state */}
          {!activeSession && !isResearching && chatHistory.length === 0 && !result && (
            <div className="flex flex-col items-center justify-center text-center animate-fadeIn pb-10">
              <div className="w-20 h-20 flex items-center justify-center rounded-3xl bg-accent/10 border border-accent/20 mb-7 mt-10">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="url(#grad)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#6366f1"/><stop offset="100%" stopColor="#a78bfa"/></linearGradient></defs>
                  <circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>
                </svg>
              </div>
              <h2 className="text-[2.5rem] font-extrabold tracking-tight bg-gradient-to-br from-accent via-accent-secondary to-text-accent bg-clip-text text-transparent bg-[length:200%_200%] animate-gradient mb-3">
                What would you like to research?
              </h2>
              <p className="text-[0.9375rem] leading-[1.7] text-text-secondary max-w-[600px] mb-12">
                Our multi-agent AI system leverages specialized agents working together to deliver deep, comprehensive research reports.
              </p>

              {/* Agent Roles Section */}
              <div className="w-full max-w-4xl text-left">
                <h3 className="text-sm font-semibold tracking-wider text-text-muted uppercase mb-4 pl-1">Meet Your AI Team</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {/* Supervisor */}
                  <div className="bg-bg-glass hover:bg-bg-glass-hover border border-border-subtle p-5 rounded-2xl transition-colors">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#f59e0b]/10 text-[#f59e0b]">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                      </div>
                      <h4 className="font-semibold text-text-primary">Supervisor</h4>
                    </div>
                    <p className="text-sm text-text-secondary leading-relaxed">The orchestrator. It manages the entire workflow, routes tasks, makes high-level decisions, and determines when research is complete.</p>
                  </div>

                  {/* Researcher */}
                  <div className="bg-bg-glass hover:bg-bg-glass-hover border border-border-subtle p-5 rounded-2xl transition-colors">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#3b82f6]/10 text-[#3b82f6]">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                      </div>
                      <h4 className="font-semibold text-text-primary">Researcher</h4>
                    </div>
                    <p className="text-sm text-text-secondary leading-relaxed">The information gatherer. It browses the internet, navigates documentation, and pulls raw data and context to answer your specific queries.</p>
                  </div>

                  {/* Analyst */}
                  <div className="bg-bg-glass hover:bg-bg-glass-hover border border-border-subtle p-5 rounded-2xl transition-colors">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#8b5cf6]/10 text-[#8b5cf6]">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                      </div>
                      <h4 className="font-semibold text-text-primary">Analyst</h4>
                    </div>
                    <p className="text-sm text-text-secondary leading-relaxed">The synthesizer. It processes the raw data found by the Researcher, extracts key insights, and structures the findings logically.</p>
                  </div>

                  {/* Critic */}
                  <div className="bg-bg-glass hover:bg-bg-glass-hover border border-border-subtle p-5 rounded-2xl transition-colors">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#ef4444]/10 text-[#ef4444]">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                      </div>
                      <h4 className="font-semibold text-text-primary">Critic</h4>
                    </div>
                    <p className="text-sm text-text-secondary leading-relaxed">The quality assurance reviewer. It evaluates the research for accuracy, completeness, and bias, sending it back if it's not up to standard.</p>
                  </div>

                  {/* Writer */}
                  <div className="bg-bg-glass hover:bg-bg-glass-hover border border-border-subtle p-5 rounded-2xl transition-colors">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#10b981]/10 text-[#10b981]">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>
                      </div>
                      <h4 className="font-semibold text-text-primary">Writer</h4>
                    </div>
                    <p className="text-sm text-text-secondary leading-relaxed">The author. It takes the approved analysis and crafts a comprehensive, well-structured, and easy-to-read final report.</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Chat History */}
          {chatHistory.map((msg, idx) => (
            <div key={idx} className={`mb-8 ${msg.type === 'user' ? 'flex flex-col items-end' : 'flex flex-col items-start'}`}>
              <div className={`max-w-[85%] rounded-2xl p-5 ${msg.type === 'user' ? 'bg-accent/10 border border-accent/20 text-text-primary' : 'bg-bg-secondary border border-border-light shadow-sm'}`}>
                {msg.type === 'user' ? (
                  <p className="text-[0.95rem] font-medium whitespace-pre-wrap">{msg.content}</p>
                ) : (
                  <div className="animate-fadeIn">
                    <ResearchResult answer={msg.content} query={activeSession?.query} hideHeader={true} />
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Pipeline */}
          {(isResearching || steps.length > 0) && (
            <div className="mb-8 animate-fadeIn">
              <AgentPipeline steps={steps} isActive={isResearching} />
            </div>
          )}

          {/* Current Active Result (if not already in chat history) */}
          {result && (!chatHistory.length || chatHistory[chatHistory.length - 1]?.content !== result.answer) && (
            <div className="animate-slideUp mb-8">
              <ResearchResult answer={result.answer} qualityScore={result.quality_score} interrupted={result.interrupted} error={result.error} query={activeSession?.query || query} />
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2.5 py-3.5 px-4.5 bg-danger-bg border border-danger/20 rounded-xl text-danger text-sm mt-4 animate-fadeIn">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <span>{error}</span>
              <button onClick={() => setError('')} className="ml-auto p-1 rounded text-danger hover:bg-danger/10 transition-all cursor-pointer">✕</button>
            </div>
          )}
        </div>

        {/* Bottom input bar */}
        <div className={`fixed bottom-0 right-0 px-12 pb-5 pt-4 bg-gradient-to-t from-bg-primary via-bg-primary/90 to-transparent z-10 transition-[left] duration-250 ease-in-out max-md:px-4 ${sidebarOpen ? 'left-[300px]' : 'left-0'}`}>
          <form onSubmit={handleStartResearch} className="max-w-[860px] mx-auto">
            {/* Toggle bar */}
            <div className="flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2 group cursor-pointer" onClick={() => setWebSearchEnabled(!webSearchEnabled)}>
                  <div className={`relative w-8 h-4.5 rounded-full transition-colors duration-200 ${webSearchEnabled ? 'bg-accent' : 'bg-border-light'}`}>
                    <div className={`absolute top-0.75 left-0.75 w-3 h-3 rounded-full bg-white shadow-sm transition-transform duration-200 ${webSearchEnabled ? 'translate-x-3.5' : 'translate-x-0'}`} />
                  </div>
                  <span className={`text-xs font-medium transition-colors ${webSearchEnabled ? 'text-text-primary' : 'text-text-muted group-hover:text-text-secondary'}`}>
                    Enable Web Search
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-text-muted font-medium uppercase tracking-wider">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                {webSearchEnabled ? 'Deep Research Active' : 'Knowledge Base Only'}
              </div>
            </div>

            <div className="flex items-center gap-3 py-2 pl-4.5 pr-3 bg-bg-secondary/85 backdrop-blur-[20px] border border-border-light rounded-2xl shadow-[0_0_0_1px_rgba(99,102,241,0.05),0_8px_32px_rgba(0,0,0,0.4)] transition-all focus-within:border-accent focus-within:shadow-[0_0_0_3px_var(--color-accent-glow),0_8px_32px_rgba(0,0,0,0.4)]">
              <svg className="text-text-muted flex-shrink-0" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input
                ref={inputRef}
                type="text"
                className="flex-1 bg-transparent border-none outline-none text-[0.9375rem] text-text-primary py-2 placeholder:text-text-muted disabled:opacity-50"
                placeholder="Ask a research question..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isResearching}
              />
              {isResearching ? (
                <button type="button" onClick={handleInterrupt} className="flex-shrink-0 flex items-center gap-2 py-2.5 px-5 text-sm font-semibold text-danger bg-danger/15 border border-danger/30 rounded-xl hover:bg-danger/25 transition-all active:scale-[0.97] cursor-pointer">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                  Stop
                </button>
              ) : (
                <button type="submit" disabled={!query.trim()} className="flex-shrink-0 flex items-center gap-2 py-2.5 px-5 text-sm font-semibold text-white bg-gradient-to-br from-accent to-accent-secondary rounded-xl shadow-[0_2px_12px_var(--color-accent-glow)] hover:shadow-[0_4px_20px_var(--color-accent-glow)] transition-all active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                  </svg>
                  Research
                </button>
              )}
            </div>
          </form>
        </div>
      </main>

      {/* Delete confirmation modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={() => setDeleteConfirm(null)}>
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          {/* Dialog */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-[400px] mx-4 bg-bg-secondary border border-border-light rounded-2xl shadow-[0_24px_80px_rgba(0,0,0,0.6)] p-6 animate-fadeInScale"
          >
            {/* Icon */}
            <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 rounded-full bg-danger-bg border border-danger/20">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                <line x1="10" y1="11" x2="10" y2="17" />
                <line x1="14" y1="11" x2="14" y2="17" />
              </svg>
            </div>
            {/* Content */}
            <h3 className="text-lg font-bold text-text-primary text-center mb-1">Delete Session</h3>
            <p className="text-sm text-text-secondary text-center mb-6 leading-relaxed">
              This will permanently delete this research session and all its data. This action cannot be undone.
            </p>
            {/* Buttons */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 py-2.5 px-4 text-sm font-semibold text-text-secondary bg-bg-glass border border-border-light rounded-xl hover:bg-bg-glass-hover hover:text-text-primary transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="flex-1 py-2.5 px-4 text-sm font-semibold text-white bg-danger border border-danger/30 rounded-xl hover:bg-danger/90 shadow-[0_2px_12px_rgba(248,113,113,0.25)] hover:shadow-[0_4px_20px_rgba(248,113,113,0.35)] transition-all active:scale-[0.97] cursor-pointer"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Document Manager Modal */}
      <DocumentManager isOpen={documentsModalOpen} onClose={() => setDocumentsModalOpen(false)} />
    </div>
  );
}
