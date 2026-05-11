import React, { useState, useEffect } from 'react';
import PipelineFeedbackWidget from '../component/PipelineFeedbackWidget';


// ── Types ─────────────────────────────────────────────────────────────────────
interface SentApplication {
  id: number;
  company_email: string;
  company_name: string;
  date_sent: string;
  followup_date: string;
  status: string;
  Unique_application_id: string;
  message_id: string;
  body_json: string;
}

interface SentFollowup {
  id: number;
  company_email: string;
  company_name: string;
  date_sent: string;
  followup_date: string;
  status: string;
  Unique_application_id: string;
  message_id: string;
  body_json: string;
  context: string;
  overall_summary: string;
  approved_at: string;
}

// Journey stages in order
const STAGES = [
  { key: 'sent', label: 'Cold Email Sent', color: 'cyan' },
  { key: 'followup_drafted', label: 'Follow-Up Drafted', color: 'amber' },
  { key: 'followup_approved', label: 'Follow-Up Approved', color: 'purple' },
] as const;

type StageKey = (typeof STAGES)[number]['key'];

const STAGE_COLORS: Record<string, string> = {
  cyan: 'bg-cyan-500   border-cyan-400   text-cyan-400   shadow-cyan-500/30',
  amber: 'bg-amber-500  border-amber-400  text-amber-400  shadow-amber-500/30',
  purple: 'bg-purple-500 border-purple-400 text-purple-400 shadow-purple-500/30',
  zinc: 'bg-zinc-700   border-zinc-600   text-zinc-500',
};

const fmtDate = (d?: string) => {
  if (!d) return '—';
  try { return new Date(d.replace(' ', 'T')).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return d; }
};

// ── Component ─────────────────────────────────────────────────────────────────
const SentPipelinePage: React.FC = () => {
  const [sentApps, setSentApps] = useState<SentApplication[]>([]);
  const [sentFollowups, setSentFollowups] = useState<SentFollowup[]>([]);
  const [reviewItems, setReviewItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sendStatus, setSendStatus] = useState<'idle' | 'success' | 'error'>('idle');

  useEffect(() => {
    Promise.all([
      fetch('/api/followups/journey').then(r => r.ok ? r.json() : []),
      fetch('/api/followups/sent-approved').then(r => r.ok ? r.json() : []),
      fetch('/api/review/all').then(r => r.ok ? r.json() : []),
    ]).then(([apps, followups, reviews]) => {
      setSentApps(apps);
      setSentFollowups(followups);
      setReviewItems(reviews);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  // Build a map: Unique_application_id → reached stages
  const followupApprovedIds = new Set(sentFollowups.map(f => f.Unique_application_id));
  const reviewFollowupIds = new Set(reviewItems.filter(r => r.type === 'followup').map(r => r.Unique_application_id));

  // Determine stage reached for a given application
  const getStage = (app: SentApplication): StageKey => {
    if (followupApprovedIds.has(app.Unique_application_id)) return 'followup_approved';
    if (reviewFollowupIds.has(app.Unique_application_id)) return 'followup_drafted';
    return 'sent';
  };

  const totalSent = sentApps.length;
  const totalFollowups = sentFollowups.length;

  return (
    <main className="h-screen w-full bg-zinc-950 text-zinc-100 font-sans selection:bg-purple-500/20" style={{ overflowY: 'auto', overflowX: 'hidden' }}>

      {/* Background */}
      <div className="fixed inset-0 z-0 bg-[radial-gradient(ellipse_at_bottom_left,_var(--tw-gradient-stops))] from-purple-950/20 via-zinc-950 to-black pointer-events-none" />

      {/* Nav */}
      <nav className="sticky top-0 z-20 w-full px-8 py-5 border-b border-zinc-800/60 bg-zinc-950/90 backdrop-blur-md flex flex-col sm:flex-row justify-between items-center gap-4">
        <h1 className="text-xl font-black tracking-widest bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent">
          FOLLOW PIPELINE<span className="text-blue-500">.</span>
        </h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 px-2 py-0.5 rounded-md font-bold">{totalSent} sent</span>
            <span className="bg-purple-500/10 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-md font-bold">{totalFollowups} follow-ups queued</span>
          </div>
          <button
            onClick={() => {
              window.history.pushState({}, '', '/dashboard');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
            className="text-sm font-bold text-zinc-300 hover:text-white transition-all border border-zinc-600/50 px-4 py-1.5 rounded-lg bg-zinc-800/60 hover:bg-zinc-700/60"
          >
            ← Dashboard
          </button>
          <button
            onClick={() => { fetch('/api/auth/logout'); window.location.href = '/'; }}
            className="text-sm font-bold text-red-400 hover:text-red-300 border border-red-500/30 px-4 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 transition-all"
          >
            Logout
          </button>
        </div>
      </nav>


      {/* Main */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-10 pb-24">

        {/* Header */}
        <div className="mb-8">
          <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-2 text-white">Application Journey</h2>
          <p className="text-zinc-400 text-base">Every sent cold email tracked end-to-end. See the full pipeline status per application, from first contact through follow-ups.</p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-3 mb-8 p-4 bg-zinc-900/40 border border-zinc-800/40 rounded-xl">
          {STAGES.map(s => {
            const [bg, , txt] = STAGE_COLORS[s.color].split(' ');
            return (
              <div key={s.key} className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${bg}`} />
                <span className={`text-xs font-semibold ${txt}`}>{s.label}</span>
              </div>
            );
          })}
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
            <span className="text-xs font-semibold text-zinc-500">Pending</span>
          </div>
        </div>

        {/* Approved follow-ups queue section */}
        {sentFollowups.length > 0 && (
          <section className="mb-10">
            <h3 className="text-sm font-bold uppercase tracking-widest text-purple-400 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
              Approved Follow-ups — Send Queue
            </h3>
            <div className="flex flex-col gap-3">
              {sentFollowups.map(fu => (
                <div key={`fu-${fu.id}`}
                  className="w-full flex flex-col p-5 bg-zinc-900/80 border-l-4 border-l-purple-500 border border-purple-500/30 rounded-xl shadow-lg shadow-purple-900/10 hover:border-purple-500/60 hover:shadow-purple-900/20 transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-md bg-purple-500/10 text-purple-300 border border-purple-500/30">
                      🔄 FOLLOW-UP QUEUED
                    </span>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                      {fu.status}
                    </span>
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-base font-bold text-zinc-100 truncate">{fu.company_name}</h4>
                      <p className="text-sm text-zinc-400 truncate">{fu.company_email}</p>
                    </div>
                    <div className="flex gap-4 text-xs text-zinc-500 shrink-0">
                      <div className="flex flex-col items-end">
                        <span className="text-zinc-600 font-medium uppercase tracking-wider text-[9px]">Approved</span>
                        <span className="text-zinc-300">{fmtDate(fu.approved_at)}</span>
                      </div>
                    </div>
                  </div>
                  {fu.Unique_application_id && (
                    <div className="mt-3 flex items-center gap-2">
                      <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-600">App ID</span>
                      <code className="text-[10px] font-mono text-purple-400/70 bg-purple-500/5 border border-purple-500/10 px-2 py-0.5 rounded-md">
                        {fu.Unique_application_id}
                      </code>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* All sent applications with journey stepper */}
        <section>
          <h3 className="text-sm font-bold uppercase tracking-widest text-cyan-400 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
            Sent Applications — Full Journey
          </h3>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="text-zinc-500 animate-pulse font-medium text-lg">Loading pipeline data…</div>
            </div>
          ) : sentApps.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 border border-dashed border-zinc-800 rounded-2xl bg-zinc-900/20">
              <span className="text-3xl mb-3">📭</span>
              <div className="text-zinc-500 font-medium">No applications sent yet.</div>
              <p className="text-zinc-600 text-sm mt-1">Approve cold emails in the Review Portal to start the pipeline.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {sentApps.map(app => {
                const currentStage = getStage(app);
                const stageIndex = STAGES.findIndex(s => s.key === currentStage);

                return (
                  <div key={`app-${app.id}`}
                    className="w-full flex flex-col p-5 bg-zinc-900/80 border-l-4 border-l-cyan-500 border border-cyan-500/30 rounded-xl shadow-lg shadow-cyan-900/10 hover:border-cyan-500/60 hover:shadow-cyan-900/20 transition-all">

                    {/* Top Row */}
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-4">
                      <div className="flex-1 min-w-0">
                        <h4 className="text-base font-bold text-zinc-100 truncate">{app.company_name}</h4>
                        <p className="text-sm text-zinc-400 truncate">{app.company_email}</p>
                      </div>
                      <div className="flex gap-4 text-xs text-zinc-500 shrink-0">
                        <div className="flex flex-col items-end">
                          <span className="text-zinc-600 font-medium uppercase tracking-wider text-[9px]">Outreach Sent</span>
                          <span className="text-zinc-300">{fmtDate(app.date_sent)}</span>
                        </div>
                        <div className="flex flex-col items-end">
                          <span className="text-zinc-600 font-medium uppercase tracking-wider text-[9px]">Follow-up Due</span>
                          <span className="text-zinc-300">{fmtDate(app.followup_date)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Unique Application ID */}
                    {app.Unique_application_id && (
                      <div className="flex items-center gap-2 mb-4">
                        <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-600">App ID</span>
                        <code className="text-[10px] font-mono text-cyan-400/70 bg-cyan-500/5 border border-cyan-500/10 px-2 py-0.5 rounded-md">
                          {app.Unique_application_id}
                        </code>
                      </div>
                    )}

                    {/* Journey Stepper */}
                    <div className="flex items-center gap-0">
                      {STAGES.map((stage, idx) => {
                        const reached = idx <= stageIndex;
                        const active = idx === stageIndex;
                        const c = reached ? STAGE_COLORS[stage.color].split(' ') : STAGE_COLORS['zinc'].split(' ');
                        const dotBg = reached ? c[0] : 'bg-zinc-800';
                        const txtCol = reached ? c[2] : 'text-zinc-600';
                        const lineCol = idx < stageIndex ? c[0] : 'bg-zinc-800';

                        return (
                          <React.Fragment key={stage.key}>
                            <div className="flex flex-col items-center">
                              <div className={`w-6 h-6 rounded-full flex items-center justify-center border-2 transition-all
                                ${dotBg} ${reached ? c[1] : 'border-zinc-700'}
                                ${active ? 'ring-2 ring-offset-2 ring-offset-zinc-900 ' + c[3] : ''}`}>
                                {reached && (
                                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                  </svg>
                                )}
                              </div>
                              <span className={`mt-1.5 text-[9px] font-bold uppercase tracking-wider text-center max-w-[72px] leading-tight ${txtCol}`}>
                                {stage.label}
                              </span>
                            </div>
                            {idx < STAGES.length - 1 && (
                              <div className={`flex-1 h-0.5 mb-5 mx-1 rounded-full transition-all ${lineCol}`} />
                            )}
                          </React.Fragment>
                        );
                      })}
                    </div>

                    {/* Status chip */}
                    <div className="mt-4 pt-3 border-t border-zinc-800/40 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-zinc-500 font-medium">{app.status}</span>
                        {!reviewFollowupIds.has(app.Unique_application_id) && !followupApprovedIds.has(app.Unique_application_id) ? (
                          <button
                            onClick={async () => {
                              try {
                                const res = await fetch(`/api/followups/generate/${app.Unique_application_id || app.id}`, { method: 'POST' });
                                const data = await res.json();
                                if (data.ok) {
                                  setSendStatus('success');
                                  alert('✅ Follow-up drafted! Check the Review Portal.');
                                  window.location.reload(); // Refresh to hide button
                                } else {
                                  setSendStatus('error');
                                  alert('❌ Error: ' + (data.error || 'Failed to generate'));
                                }
                              } catch (e) {
                                alert('❌ Failed to trigger follow-up generation.');
                              }
                            }}
                            className="text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/20 transition-all"
                          >
                            ⚡ Follow-up Now
                          </button>
                        ) : (
                          <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/25">
                            ⏳ Draft in Review
                          </span>
                        )}
                      </div>
                      {currentStage === 'followup_approved' && (
                        <div className="flex flex-col items-end">
                          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                            Follow-up queued ✓
                          </span>
                          {sendStatus === 'success' && (
                            <PipelineFeedbackWidget 
                              pipelineStage="followup"
                              actionDescription={`Follow-up scheduled for: ${app.company_name}`}
                              outcomeMessage="Follow-up queued successfully"
                            />
                          )}
                        </div>
                      )}

                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
};

export default SentPipelinePage;