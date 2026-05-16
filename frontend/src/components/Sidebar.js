'use client';

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
  onNewResearch,
  isOpen,
  onToggle,
  loading,
  user,
  onLogout,
  onOpenDocuments,
}) {
  const formatDate = (iso) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const truncateQuery = (q, max = 50) =>
    q.length > max ? q.slice(0, max) + '…' : q;

  return (
    <aside className={`fixed left-0 top-0 bottom-0 w-[300px] bg-[rgba(15,20,35,0.95)] backdrop-blur-[20px] border-r border-border-subtle flex flex-col z-20 transition-transform duration-250 ease-in-out ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-border-subtle">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 flex items-center justify-center rounded-[10px] bg-gradient-to-br from-accent to-accent-secondary text-white">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
              <path d="M2 12h20" />
            </svg>
          </div>
          <span className="font-bold text-[0.9375rem] tracking-tight">Research Agent</span>
        </div>
        <button onClick={onToggle} aria-label="Close sidebar" className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-glass-hover transition-all cursor-pointer">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="11 17 6 12 11 7" />
            <polyline points="18 17 13 12 18 7" />
          </svg>
        </button>
      </div>

      {/* New research & Documents */}
      <div className="flex flex-col gap-2 p-4">
        <button
          onClick={onNewResearch}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-5 text-sm font-semibold text-white bg-gradient-to-br from-accent to-accent-secondary rounded-xl shadow-[0_2px_12px_var(--color-accent-glow)] hover:shadow-[0_4px_20px_var(--color-accent-glow)] transition-all active:scale-[0.97] cursor-pointer"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Research
        </button>
        <button
          onClick={onOpenDocuments}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-5 text-sm font-semibold text-text-primary bg-bg-glass border border-border-subtle rounded-xl hover:bg-bg-glass-hover transition-all active:scale-[0.97] cursor-pointer"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
            <polyline points="13 2 13 9 20 9" />
          </svg>
          Knowledge Base
        </button>
      </div>

      {/* Sessions label */}
      <div className="flex items-center justify-between px-4 mb-2">
        <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">History</span>
        <span className="text-xs font-semibold text-text-muted bg-bg-glass px-2 py-0.5 rounded-full">{sessions.length}</span>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-2">
        {loading ? (
          <div className="flex flex-col gap-2 px-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-[60px] rounded-xl bg-gradient-to-r from-bg-glass via-bg-glass-hover to-bg-glass bg-[length:200%_100%] animate-[shimmer_1.5s_ease-in-out_infinite]" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 px-5 text-text-muted text-[0.8125rem]">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
            </svg>
            <span>No research sessions yet</span>
          </div>
        ) : (
          sessions.map((s) => (
            <div
              key={s.session_id}
              onClick={() => onSelect(s)}
              className={`group flex items-start gap-2 p-3 rounded-xl cursor-pointer transition-all mb-0.5 ${
                s.session_id === activeSessionId
                  ? 'bg-accent/10 border border-accent/20'
                  : 'hover:bg-bg-glass-hover border border-transparent'
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="text-[0.8125rem] font-medium text-text-primary truncate mb-1.5">{truncateQuery(s.query)}</div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full border ${
                    s.status === 'completed'
                      ? 'bg-success-bg text-success border-success/20'
                      : s.status === 'running'
                        ? 'bg-warning-bg text-warning border-warning/20'
                        : 'bg-info-bg text-info border-info/20'
                  }`}>
                    {s.status}
                  </span>
                  <span className="text-xs text-text-muted">{formatDate(s.created_at)}</span>
                </div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(s.session_id); }}
                aria-label="Delete session"
                className="opacity-0 group-hover:opacity-100 p-1 rounded text-text-muted hover:text-danger hover:bg-danger-bg transition-all flex-shrink-0 mt-0.5 cursor-pointer"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between p-4 border-t border-border-subtle">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-[34px] h-[34px] flex items-center justify-center rounded-[10px] bg-gradient-to-br from-accent to-accent-secondary text-white font-bold text-[0.8125rem] flex-shrink-0">
            {user?.username?.[0]?.toUpperCase() || '?'}
          </div>
          <div className="min-w-0">
            <div className="text-[0.8125rem] font-semibold text-text-primary truncate">{user?.username}</div>
            <div className="text-xs text-text-muted truncate">{user?.email}</div>
          </div>
        </div>
        <button onClick={onLogout} aria-label="Logout" className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-glass-hover transition-all cursor-pointer">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
