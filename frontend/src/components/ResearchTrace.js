import React, { useState, useEffect } from 'react';
import { getResearchLogs } from '@/lib/api';

const ResearchTrace = ({ sessionId, isOpen, onClose }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState(null);

  useEffect(() => {
    if (isOpen && sessionId) {
      fetchLogs();
    }
  }, [isOpen, sessionId]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await getResearchLogs(sessionId);
      setLogs(data.logs || []);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-bg-glass border border-border-subtle w-full max-w-4xl h-[80vh] rounded-3xl overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border-subtle flex items-center justify-between bg-bg-glass/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-accent/10 text-accent">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
            </div>
            <div>
              <h3 className="font-bold text-text-primary">Research Trace & Debug</h3>
              <p className="text-xs text-text-muted">Observability logs for session: {sessionId}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-xl transition-colors text-text-muted hover:text-text-primary"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
          {loading ? (
            <div className="h-full flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
            </div>
          ) : logs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-text-muted">
              <p>No trace logs available yet.</p>
              <p className="text-xs">Agents log traces after completing their turns.</p>
            </div>
          ) : (
            logs.map((log, index) => (
              <div 
                key={index} 
                className={`border rounded-2xl overflow-hidden transition-all ${
                  expandedIndex === index ? 'border-accent/40 bg-accent/5' : 'border-border-subtle bg-bg-glass/30'
                }`}
              >
                <button 
                  onClick={() => setExpandedIndex(expandedIndex === index ? null : index)}
                  className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-white/10 text-text-secondary">
                      {log.agent}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                      log.type === 'error' ? 'bg-red-500/20 text-red-400' : 
                      log.type === 'prompt' ? 'bg-blue-500/20 text-blue-400' :
                      log.type === 'retrieval' ? 'bg-green-500/20 text-green-400' :
                      'bg-white/5 text-text-muted'
                    }`}>
                      {log.type}
                    </span>
                    <span className="text-xs font-mono text-text-muted">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <svg 
                    className={`transform transition-transform ${expandedIndex === index ? 'rotate-180' : ''}`}
                    width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  >
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>
                
                {expandedIndex === index && (
                  <div className="px-4 pb-4 animate-in fade-in slide-in-from-top-1 duration-200">
                    <div className="bg-black/40 rounded-xl p-4 font-mono text-[11px] text-text-secondary overflow-x-auto whitespace-pre-wrap max-h-96">
                      {JSON.stringify(log.data, null, 2)}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border-subtle bg-bg-glass/50 flex justify-between items-center">
          <span className="text-[10px] text-text-muted font-mono uppercase tracking-widest">
            Evidence-Oriented Research Architecture
          </span>
          <button 
            onClick={fetchLogs}
            className="text-[11px] font-semibold text-accent hover:underline flex items-center gap-1"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
            Refresh Logs
          </button>
        </div>
      </div>
    </div>
  );
};

export default ResearchTrace;
