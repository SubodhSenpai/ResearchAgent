'use client';

export default function ResearchResult({ answer, qualityScore, interrupted, error, query, hideHeader }) {
  const scorePercent = Math.round((qualityScore || 0) * 100);
  const scoreColor =
    scorePercent >= 80 ? 'var(--color-success)' :
    scorePercent >= 60 ? 'var(--color-warning)' :
    'var(--color-danger)';

  return (
    <div className={`bg-bg-card backdrop-blur-[24px] border border-border-subtle rounded-3xl ${hideHeader ? 'p-6' : 'p-8'} shadow-[0_10px_40px_rgba(0,0,0,0.5)]`}>
      {/* Header */}
      {!hideHeader && (
        <>
          <div className="flex items-start justify-between gap-6 max-sm:flex-col">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-text-primary mb-1">Research Results</h2>
              <p className="text-xs text-text-muted">{query}</p>
            </div>
            <div className="text-center flex-shrink-0 p-3 px-4 bg-bg-glass border border-border-subtle rounded-2xl">
              <div className="text-[1.75rem] font-extrabold font-mono leading-none mb-1" style={{ color: scoreColor }}>
                {scorePercent}%
              </div>
              <div className="text-xs text-text-muted mb-2">Quality</div>
              <div className="h-1 w-20 bg-bg-glass rounded-sm overflow-hidden">
                <div
                  className="h-full rounded-sm transition-[width] duration-500 ease-out"
                  style={{ width: `${scorePercent}%`, background: scoreColor }}
                />
              </div>
            </div>
          </div>

          {/* Badges */}
          <div className="flex gap-2 flex-wrap mt-4">
            {interrupted && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-warning-bg text-warning border border-warning/20">⚠️ Research was interrupted</span>
            )}
            {error && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-danger-bg text-danger border border-danger/20">❌ Error occurred</span>
            )}
            {!interrupted && !error && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-success-bg text-success border border-success/20">✅ Completed successfully</span>
            )}
          </div>

          <hr className="h-px bg-border-subtle my-6 border-none" />
        </>
      )}

      {/* Answer */}
      <div className="text-[0.9375rem] leading-[1.8] text-text-secondary mt-2">
        {answer ? (
          answer.split('\n').map((paragraph, i) => {
            const trimmed = paragraph.trim();
            if (!trimmed) return null;

            if (trimmed.startsWith('### ')) return <h3 key={i} className="text-text-primary font-semibold mt-6 mb-3">{trimmed.slice(4)}</h3>;
            if (trimmed.startsWith('## '))  return <h2 key={i} className="text-text-primary font-semibold text-lg mt-6 mb-3">{trimmed.slice(3)}</h2>;
            if (trimmed.startsWith('# '))   return <h1 key={i} className="text-text-primary font-bold text-xl mt-6 mb-3">{trimmed.slice(2)}</h1>;

            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
              return (
                <div key={i} className="flex gap-2 items-start mb-2">
                  <span className="text-accent font-bold flex-shrink-0 mt-px">•</span>
                  <span>{trimmed.slice(2)}</span>
                </div>
              );
            }

            const numMatch = trimmed.match(/^(\d+)\.\s(.+)/);
            if (numMatch) {
              return (
                <div key={i} className="flex gap-2 items-start mb-2">
                  <span className="text-accent font-semibold font-mono flex-shrink-0 min-w-[20px]">{numMatch[1]}.</span>
                  <span>{numMatch[2]}</span>
                </div>
              );
            }

            const formatted = trimmed.replace(/\*\*(.+?)\*\*/g, '<strong class="text-text-primary">$1</strong>');
            return <p key={i} className="mb-4" dangerouslySetInnerHTML={{ __html: formatted }} />;
          })
        ) : (
          <p className="text-text-muted">No answer generated.</p>
        )}
      </div>
    </div>
  );
}
