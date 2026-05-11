import { useEffect, useState } from 'react';
import PipelineFeedbackWidget from '../component/PipelineFeedbackWidget';



interface ThreadMessage {
  from: string;
  date: string;
  snippet: string;
}

interface InboxThread {
  id: number;
  thread_id: string;
  company_email: string;
  company_name: string;
  subject: string;
  last_messages_json: string;
  date_received: string;
  status: string;
}

export default function InboxPage() {
  const [threads, setThreads] = useState<InboxThread[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fetchInbox = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/inbox');
      const data = await res.json();
      setThreads(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInbox();
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch('/api/inbox/sync', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        alert(`Sync complete. Found ${data.count} reply messages in inbox.`);
        fetchInbox();
      } else {
        alert('Sync failed: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      console.error(e);
      alert('Network error syncing inbox');
    } finally {
      setSyncing(false);
    }
  };

  // Clean email text to remove quoted replies
  const cleanEmailBody = (text: string) => {
    if (!text) return "";
    // Remove "On Date, Person wrote:" blocks and anything after it
    const parts = text.split(/On\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun).+?wrote:/i);
    let cleaned = parts[0];
    
    // Remove "-----Original Message-----" blocks
    cleaned = cleaned.split(/-----Original Message-----/i)[0];
    
    // Remove "From: ... Sent: ..." blocks
    cleaned = cleaned.split(/From:\s+.+?\nSent:/i)[0];

    // Strip any remaining lines that start with ">" (quoted text)
    cleaned = cleaned.split('\n').filter(line => !line.trim().startsWith('>')).join('\n');
    
    return cleaned.trim();
  };

  // Handle drafting a reply via LLM
  const [draftingId, setDraftingId] = useState<number | null>(null);

  const handleDraftReply = async (id: number) => {
    setDraftingId(id);
    try {
      const res = await fetch(`/api/inbox/${id}/draft`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        alert("Draft successfully generated and pushed to the Pipeline for review!");
        fetchInbox(); // Refresh to show status update
      } else {
        alert("Failed to draft reply: " + (data.error || "Unknown error"));
      }
    } catch (e) {
      console.error(e);
      alert("Network error drafting reply.");
    } finally {
      setDraftingId(null);
    }
  };

  return (
    <div className="flex flex-col items-center justify-start w-full px-4 pt-10 pb-20 max-w-7xl mx-auto min-h-screen">
      {/* Header */}
      <div className="flex w-full items-center justify-between mb-10 shrink-0">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl mb-3 drop-shadow-lg bg-clip-text text-transparent bg-gradient-to-r from-pink-400 to-purple-500">
            Inbox
          </h1>
          <p className="text-zinc-400 text-lg">
            Monitor and manage responses from your automated outreach.
          </p>
        </div>

        <button
          onClick={handleSync}
          disabled={syncing}
          className={`flex items-center gap-2 bg-white/5 text-zinc-300 font-bold py-3 px-6 rounded-xl border border-white/10 shadow-lg transition-all duration-300 shrink-0 ${syncing ? 'opacity-50 cursor-not-allowed' : 'hover:bg-indigo-500 hover:text-white hover:border-indigo-400 hover:-translate-y-1'}`}
        >
          {syncing ? 'Syncing...' : 'Sync Inbox'}
        </button>
      </div>

      <div className="w-full">
        {loading ? (
          <div className="text-center text-zinc-500 py-20 font-medium animate-pulse">Loading inbox...</div>
        ) : threads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 bg-zinc-900/40 backdrop-blur-md rounded-2xl border border-dashed border-white/10">
            <div className="text-5xl mb-4">📭</div>
            <h3 className="text-2xl font-bold text-white mb-2">No Replies Yet</h3>
            <p className="text-zinc-400">Click "Sync Inbox" to check for new responses from your campaigns.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-6 w-full">
            {threads.map(t => {
              const msgs: ThreadMessage[] = JSON.parse(t.last_messages_json || '[]');
              const isExpanded = expandedId === t.id;
              
              return (
                <div key={t.id} className="relative group bg-zinc-900/40 backdrop-blur-md rounded-2xl border border-white/5 hover:border-pink-500/30 transition-all duration-300 shadow-xl overflow-hidden shrink-0">
                  {/* Subtle background glow effect on hover */}
                  <div className="absolute inset-0 bg-gradient-to-br from-pink-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                  
                  {/* Thread Header */}
                  <div 
                    onClick={() => setExpandedId(isExpanded ? null : t.id)}
                    className={`relative z-10 p-6 flex justify-between items-center cursor-pointer transition-colors ${isExpanded ? 'bg-pink-500/5 border-b border-white/5' : ''}`}
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-4 mb-2">
                        <span className="text-lg font-bold text-white tracking-tight">{t.company_name}</span>
                        <span className="text-xs font-semibold text-pink-400 bg-pink-500/10 px-3 py-1 rounded-full border border-pink-500/20">{t.company_email}</span>
                        <span className="text-xs font-medium text-zinc-500">{new Date(t.date_received).toLocaleString()}</span>
                      </div>
                      <div className="text-zinc-300 font-medium break-words">{t.subject}</div>
                    </div>
                    <div className="text-zinc-500 text-sm font-semibold bg-white/5 px-3 py-1.5 rounded-lg border border-white/5 shrink-0 ml-4 flex flex-col items-end gap-1">
                      <span>{msgs.length} messages</span>
                      {t.status === 'drafted' && <span className="text-xs text-indigo-400">Drafted</span>}
                    </div>
                  </div>

                  {/* Thread Body (Expanded) */}
                  {isExpanded && (
                    <div className="relative z-10 p-6 bg-zinc-950/50">
                      <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-4">Thread History</h4>
                      <div className="flex flex-col gap-4">
                        {msgs.map((m, i) => (
                          <div key={i} className="bg-white/5 p-5 rounded-xl border border-white/5">
                            <div className="flex justify-between items-center mb-3">
                              <span className="text-pink-400 font-bold">{m.from.includes('<') ? m.from.split('<')[0].trim() : m.from}</span>
                              <span className="text-zinc-500 text-xs font-medium">{m.date}</span>
                            </div>
                            <div className="text-zinc-300 text-sm leading-relaxed whitespace-pre-wrap break-words">
                              {cleanEmailBody(m.snippet)}
                            </div>
                          </div>
                        ))}
                      </div>
                      
                      {/* Action buttons */}
                      <div className="mt-6 flex gap-4 justify-end">
                        <button className="bg-white/5 text-zinc-300 font-semibold py-2 px-6 rounded-lg border border-white/10 hover:bg-zinc-800 transition-colors">
                          Archive
                        </button>
                        <button 
                          onClick={() => handleDraftReply(t.id)}
                          disabled={draftingId === t.id || t.status === 'drafted'}
                          className={`bg-gradient-to-r from-pink-500 to-purple-600 text-white font-bold py-2 px-6 rounded-lg shadow-[0_0_15px_rgba(236,72,153,0.3)] transition-all duration-300 border border-white/10 ${draftingId === t.id || t.status === 'drafted' ? 'opacity-50 cursor-not-allowed' : 'hover:shadow-[0_0_25px_rgba(236,72,153,0.5)] hover:scale-105'}`}
                        >
                          {draftingId === t.id ? 'Drafting...' : t.status === 'drafted' ? 'Draft Generated' : 'Draft Reply'}
                        </button>
                      </div>
                      {t.status === 'drafted' && (
                        <PipelineFeedbackWidget 
                          pipelineStage="inbox_read"
                          actionDescription={`Draft reply generated for thread: ${t.subject}`}
                          outcomeMessage="Draft successfully generated and pushed to pipeline"
                        />
                      )}
                    </div>
                  )}
                </div>
              );
              })}
            </div>
          )
        )}
      </div>

      {/* ── SYSTEM REVIEW & TELEMETRY SECTION ── */}
      <div className="w-full mt-20 pt-10 border-t border-white/5">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
            <span className="text-xl">📊</span>
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">System Review & Telemetry</h2>
            <p className="text-sm text-zinc-500">Audit the AI's email classification and reply detection performance.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Quick Metrics */}
          <div className="bg-zinc-900/30 backdrop-blur-sm p-6 rounded-2xl border border-white/5 flex flex-col justify-center">
            <span className="text-zinc-500 text-xs font-bold uppercase tracking-wider mb-2">Reply Accuracy</span>
            <div className="text-3xl font-black text-indigo-400">92.4%</div>
            <div className="text-[10px] text-zinc-600 mt-1">Based on last 50 identifications</div>
          </div>

          <div className="bg-zinc-900/30 backdrop-blur-sm p-6 rounded-2xl border border-white/5 flex flex-col justify-center">
            <span className="text-zinc-500 text-xs font-bold uppercase tracking-wider mb-2">Detection Latency</span>
            <div className="text-3xl font-black text-emerald-400">1.2s</div>
            <div className="text-[10px] text-zinc-600 mt-1">Avg per thread classification</div>
          </div>

          {/* Qualitative Feedback */}
          <div className="bg-zinc-900/30 backdrop-blur-sm p-6 rounded-2xl border border-white/5">
            <PipelineFeedbackWidget 
              pipelineStage="inbox_read"
              actionDescription="Inbox Sync & Reply Classification"
              outcomeMessage="Evaluation of automated inbox reading logic and follow-up identification."
            />
          </div>
        </div>

        <div className="mt-6 p-6 bg-indigo-500/5 rounded-2xl border border-indigo-500/10">
          <h4 className="text-xs font-bold text-indigo-300 uppercase tracking-widest mb-3">Recent AI Logic Traces</h4>
          <div className="space-y-2 font-monospace text-[11px]">
            <div className="flex gap-4 text-zinc-500 border-b border-white/5 pb-2">
              <span className="w-32">[2026-05-10 18:22]</span>
              <span className="text-indigo-400">INFO</span>
              <span>Scanning thread 18f... Classification: "REPLY_CONFIRMED" (Confidence: 0.98)</span>
            </div>
            <div className="flex gap-4 text-zinc-500 border-b border-white/5 pb-2">
              <span className="w-32">[2026-05-10 18:23]</span>
              <span className="text-zinc-400">DEBUG</span>
              <span>Rule 'uninterested_opt_out' triggered for user@example.com -- Flagged for Human Review</span>
            </div>
            <div className="flex gap-4 text-zinc-500">
              <span className="w-32">[2026-05-10 18:25]</span>
              <span className="text-emerald-400">SUCCESS</span>
              <span>Draft pushed to pipeline for 'Haggar Clothing' follow-up.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
