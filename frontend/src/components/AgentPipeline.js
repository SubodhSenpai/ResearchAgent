'use client';

const AGENT_META = {
  memory_check: { icon: '🧠', label: 'Memory Check', color: '#ec4899' },
  supervisor:   { icon: '👔', label: 'Supervisor',   color: '#f59e0b' },
  researcher:   { icon: '🔍', label: 'Researcher',   color: '#3b82f6' },
  analyst:      { icon: '📊', label: 'Analyst',      color: '#8b5cf6' },
  critic:       { icon: '⚖️', label: 'Critic',       color: '#ef4444' },
  validator:    { icon: '🛡️', label: 'Evidence Auditor', color: '#6366f1' },
  writer:       { icon: '✍️', label: 'Writer',       color: '#10b981' },
  save_memory:  { icon: '💾', label: 'Saving Session',color: '#ec4899' },
  interrupt_check: { icon: '⏸️', label: 'Interrupt Check', color: '#f59e0b' },
};

export default function AgentPipeline({ steps, isActive }) {
  return (
    <div className="bg-bg-glass backdrop-blur-[16px] border border-border-subtle rounded-2xl p-5 px-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
          {isActive && (
            <span className="w-4 h-4 border-2 border-border-subtle border-t-accent rounded-full animate-spin-fast" />
          )}
          Agent Pipeline
        </h3>
        {isActive && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-warning-bg text-warning border border-warning/20">
            <span className="flex gap-1">
              <span className="w-1 h-1 rounded-full bg-warning animate-[dotPulse_1.4s_ease-in-out_infinite]" />
              <span className="w-1 h-1 rounded-full bg-warning animate-[dotPulse_1.4s_ease-in-out_infinite_0.16s]" />
              <span className="w-1 h-1 rounded-full bg-warning animate-[dotPulse_1.4s_ease-in-out_infinite_0.32s]" />
            </span>
            Processing
          </span>
        )}
      </div>

      {/* Timeline */}
      <div className="flex flex-col">
        {steps.map((step, i) => {
          const meta = AGENT_META[step.node] || { icon: '⚙️', label: step.label, color: '#6366f1' };
          const isLast = i === steps.length - 1;

          return (
            <div key={i} className="animate-slideRight" style={{ animationDelay: `${i * 0.05}s` }}>
              {/* Connector */}
              {i > 0 && <div className="w-0.5 h-3 bg-border-light ml-[11px]" />}

              {/* Node */}
              <div className="flex items-center gap-3">
                <div
                  className={`w-6 h-6 rounded-full flex-shrink-0 border-[3px] border-bg-primary ${isLast && isActive ? 'animate-pulse-dot' : ''}`}
                  style={{
                    background: meta.color,
                    boxShadow: isLast && isActive ? `0 0 12px ${meta.color}` : 'none',
                  }}
                />
                <div className="flex items-center gap-2 py-2 px-3.5 bg-bg-glass border border-border-subtle rounded-xl flex-1">
                  <span className="text-base">{meta.icon}</span>
                  <span className="text-[0.8125rem] font-semibold text-text-primary">{meta.label}</span>
                    <span className="text-[0.6875rem] text-text-muted font-mono ml-auto bg-bg-glass px-2 py-0.5 rounded-full flex gap-3">
                      {step.completeness_score !== undefined && step.completeness_score !== null && (
                        <span className="text-accent font-bold">
                          Completeness: {step.completeness_score}%
                        </span>
                      )}
                      {step.iteration > 0 && <span>iter {step.iteration}</span>}
                    </span>
                </div>
              </div>
            </div>
          );
        })}

        {/* Pending indicator */}
        {isActive && steps.length > 0 && (
          <div className="animate-slideRight">
            <div className="w-0.5 h-3 bg-border-light ml-[11px]" />
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-full flex-shrink-0 border-2 border-dashed border-border-light bg-bg-glass animate-pulse-dot" />
              <div className="flex items-center gap-2 py-2 px-3.5 bg-bg-glass border border-border-subtle rounded-xl flex-1">
                <span className="text-[0.8125rem] font-semibold text-text-muted">Waiting for next agent...</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
