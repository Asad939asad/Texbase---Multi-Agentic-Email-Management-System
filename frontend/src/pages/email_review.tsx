import React, { useState, useEffect } from 'react';
import FollowupFeedbackWidget from '../component/FollowupFeedbackWidget';

// ── Types ─────────────────────────────────────────────────────────────────────
export interface ReviewRecord {
  // Cold email fields (new outreach schema)
  id: number;
  body_json: string;
  timestamp?: string;
  followup_date?: string;
  status: string;
  company_name?: string;       // NEW — replaces 'role'
  generated_subject?: string;  // NEW — replaces 'date_applied'
  company_email: string;
  website?: string;
  hs_codes?: string;
  // Legacy fields (kept for follow-up compatibility)
  role?: string;
  date_applied?: string;
  // Follow-up only fields
  Unique_application_id?: string;
  overall_summary?: string;
  context?: string;
  message_id?: string;
  // Injected by backend
  type: 'cold' | 'followup';
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const TYPE_CONFIG = {
  cold: {
    label: 'COLD EMAIL',
    badgeBg: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    border: 'border-l-cyan-500',
    glow: 'hover:shadow-cyan-900/20',
    pill: 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30',
  },
  followup: {
    label: 'FOLLOW-UP',
    badgeBg: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    border: 'border-l-purple-500',
    glow: 'hover:shadow-purple-900/20',
    pill: 'bg-purple-500/10 text-purple-400 border border-purple-500/30',
  },
} as const;

const getStatusStyle = (status: string) => {
  const s = status.toLowerCase();
  if (s.includes('approved') || s.includes('ready')) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25';
  if (s.includes('reject')) return 'bg-red-500/10 text-red-400 border-red-500/25';
  if (s.includes('review') || s.includes('pending') || s.includes('draft')) return 'bg-amber-500/10 text-amber-400 border-amber-500/25';
  return 'bg-zinc-500/10 text-zinc-400 border-zinc-500/25';
};

const fmtDate = (d?: string) => {
  if (!d) return '—';
  try { return new Date(d.replace(' ', 'T')).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return d; }
};

// ── Component ─────────────────────────────────────────────────────────────────
const TrackingDashboard: React.FC = () => {
  const [records, setRecords] = useState<ReviewRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'cold' | 'followup'>('all');
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [sendEnabled, setSendEnabled] = useState(false);
  const [switchLoading, setSwitchLoading] = useState(false);

  // Inline Editing State
  const [editingEmailId, setEditingEmailId] = useState<number | null>(null);
  const [tempEmail, setTempEmail] = useState('');

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchAll = () => {
    setLoading(true);
    fetch('http://localhost:8000/api/review/all')
      .then(r => { if (!r.ok) throw new Error('Failed to fetch'); return r.json(); })
      .then(data => { setRecords(data); setLoading(false); })
      .catch(err => { console.error(err); setLoading(false); });
  };

  useEffect(() => {
    fetchAll();
    // Load current send-switch state from server
    fetch('http://localhost:8000/api/settings/send-switch')
      .then(r => r.json())
      .then(d => setSendEnabled(d.enabled ?? false))
      .catch(() => { });
  }, []);

  const toggleSend = async () => {
    setSwitchLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/settings/send-switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !sendEnabled }),
      });
      const data = await res.json();
      if (data.ok) {
        setSendEnabled(data.enabled);
        showToast(data.enabled ? 'Email sending ENABLED' : 'Email sending DISABLED', true);
      }
    } catch { showToast('Failed to toggle switch', false); }
    finally { setSwitchLoading(false); }
  };

  const updateMetadata = async (id: number, field: string, value: string) => {
    const res = await fetch(`http://localhost:8000/api/tracking/${id}/metadata`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ field, value, dbType: 'review' }),
    });
    return res.json();
  };

  const handleSaveEmail = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!tempEmail.includes('@')) {
      showToast("Please enter a valid email", false);
      return;
    }
    try {
      const res = await updateMetadata(id, 'company_email', tempEmail);
      if (res.ok) {
        showToast("Email updated", true);
        setEditingEmailId(null);
        setTempEmail('');
        fetchAll();
      } else {
        showToast(res.error || "Update failed", false);
      }
    } catch { showToast("Network error", false); }
  };

  const handleApprove = async (record: ReviewRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    if (record.company_email === 'not updated') {
      showToast("Recipient email is required. Please add it first.", false);
      return;
    }
    setActionLoading(record.id);
    const url = record.type === 'cold'
      ? `http://localhost:8000/api/review/cold/${record.id}/approve`
      : `http://localhost:8000/api/review/followup/${record.id}/approve`;
    try {
      const res = await fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const data = await res.json();
      if (data.ok) { showToast('Approved — moved to send queue', true); fetchAll(); }
      else { showToast(`${data.error || 'Approval failed'}`, false); }
    } catch { showToast('Network error', false); }
    finally { setActionLoading(null); }
  };

  const handleReject = async (record: ReviewRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(record.id);
    const url = record.type === 'cold'
      ? `http://localhost:8000/api/review/cold/${record.id}/reject`
      : `http://localhost:8000/api/review/followup/${record.id}/reject`;
    try {
      const res = await fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const data = await res.json();
      if (data.ok) { showToast('Rejected', true); fetchAll(); }
      else { showToast(`${data.error || 'Reject failed'}`, false); }
    } catch { showToast('Network error', false); }
    finally { setActionLoading(null); }
  };

  const handleDelete = async (record: ReviewRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Permanently delete this record? This will end its journey.')) return;
    setActionLoading(record.id);
    const url = record.type === 'cold'
      ? `http://localhost:8000/api/review/cold/${record.id}`
      : `http://localhost:8000/api/review/followup/${record.id}`;
    try {
      const res = await fetch(url, { method: 'DELETE' });
      const data = await res.json();
      if (data.ok) { showToast('Deleted permanently', true); fetchAll(); }
      else { showToast(`${data.error || 'Delete failed'}`, false); }
    } catch { showToast('Network error', false); }
    finally { setActionLoading(null); }
  };

  const openEditor = (record: ReviewRecord) => {
    const params = new URLSearchParams({ id: String(record.id), type: record.type });
    window.history.pushState({}, '', `/editor?${params.toString()}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const displayed = records.filter(r => filter === 'all' || r.type === filter);
  const coldCount = records.filter(r => r.type === 'cold').length;
  const followupCount = records.filter(r => r.type === 'followup').length;

  return (
    <main className="h-screen w-full bg-zinc-950 text-zinc-100 font-sans selection:bg-blue-500/30" style={{ overflowY: 'auto', overflowX: 'hidden' }}>

      {/* Gradient background */}
      <div className="fixed inset-0 z-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-zinc-900 via-zinc-950 to-black pointer-events-none" />

      {/* Toast */}
      {toast && (
        <div className={`fixed top-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm font-semibold shadow-2xl border transition-all
          ${toast.ok ? 'bg-zinc-900 border-emerald-500/40 text-emerald-300' : 'bg-zinc-900 border-red-500/40 text-red-300'}`}>
          {toast.msg}
        </div>
      )}

      {/* Nav */}
      <nav className="sticky top-0 z-20 w-full px-8 py-5 border-b border-zinc-800/50 bg-zinc-950/90 backdrop-blur-md flex flex-col sm:flex-row justify-between items-center gap-4">
        <h1 className="text-xl font-black tracking-widest bg-gradient-to-r from-emerald-400 to-cyan-500 bg-clip-text text-transparent">
          AI REVIEW PORTAL<span className="text-blue-500">.</span>
        </h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-400">
            <span className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 px-2 py-0.5 rounded-md font-bold">{coldCount} cold</span>
            <span className="bg-purple-500/10 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-md font-bold">{followupCount} follow-up</span>
          </div>

          {/* Send switch */}
          <button
            onClick={toggleSend}
            disabled={switchLoading}
            title={sendEnabled ? 'Click to DISABLE email sending' : 'Click to ENABLE email sending'}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50
              ${sendEnabled
                ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25'
                : 'bg-zinc-800/60 border-zinc-600/40 text-zinc-400 hover:bg-zinc-700/60'}`}
          >
            <span className={`w-2 h-2 rounded-full transition-all ${sendEnabled ? 'bg-emerald-400 shadow-[0_0_6px_2px_rgba(52,211,153,0.5)]' : 'bg-zinc-600'}`} />
            {sendEnabled ? 'Sending ON' : 'Sending OFF'}
          </button>

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
            onClick={() => { fetch('http://localhost:8000/api/auth/logout'); window.location.href = '/'; }}
            className="text-sm font-bold text-red-400 hover:text-red-300 transition-all border border-red-500/30 px-4 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20"
          >
            Logout
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-10 pb-24">

        {/* Header */}
        <div className="mb-8">
          <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-2 text-white">Application Queue</h2>
          <p className="text-zinc-400 text-base">Review AI-drafted emails. <span className="text-cyan-400 font-semibold">Cyan</span> = cold emails · <span className="text-purple-400 font-semibold">Purple</span> = follow-ups. Click any card to open the editor.</p>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-8">
          {(['all', 'cold', 'followup'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-all
                ${filter === f
                  ? f === 'cold' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300'
                    : f === 'followup' ? 'bg-purple-500/20 border-purple-500/50 text-purple-300'
                      : 'bg-zinc-700/60 border-zinc-500/50 text-zinc-200'
                  : 'bg-zinc-900/40 border-zinc-700/50 text-zinc-500 hover:text-zinc-300'
                }`}
            >
              {f === 'all' ? `All (${records.length})` : f === 'cold' ? `Cold (${coldCount})` : `Follow-ups (${followupCount})`}
            </button>
          ))}
        </div>

        {/* List */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-zinc-500 animate-pulse font-medium text-lg">Loading review queue…</div>
          </div>
        ) : displayed.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 border border-dashed border-zinc-800 rounded-2xl bg-zinc-900/20">
            <span className="text-3xl mb-3">📂</span>
            <div className="text-zinc-500 font-medium">No items in queue.</div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {displayed.map(record => {
              const cfg = TYPE_CONFIG[record.type];
              const isLoading = actionLoading === record.id;
              const isTerminal = record.status.toLowerCase().includes('approved') ||
                record.status.toLowerCase().includes('reject') ||
                record.status.toLowerCase().includes('ready');
              return (
                <div
                  key={`${record.type}-${record.id}`}
                  onClick={() => openEditor(record)}
                  className={`group w-full flex flex-col p-5 bg-zinc-900/60 backdrop-blur-xl border-l-4 border border-zinc-700/60 rounded-xl
                    hover:bg-zinc-800/70 hover:border-zinc-500 hover:scale-[1.005] transition-all duration-200 cursor-pointer
                    shadow-lg hover:shadow-2xl ${cfg.border} ${cfg.glow}`}
                >
                  {/* Row 1: Type flag + Status badge */}
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-md border ${cfg.pill}`}>
                      {cfg.label}
                    </span>
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-md border ${getStatusStyle(record.status)}`}>
                      {record.status}
                    </span>
                  </div>

                  {/* Row 2: Company Name + Subject / Role */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className={`text-lg font-bold truncate mb-0.5 group-hover:${record.type === 'cold' ? 'text-cyan-400' : 'text-purple-400'} transition-colors`}>
                        {record.company_name || record.role || '—'}
                      </h3>
                      {record.type === 'cold' && record.generated_subject && (
                        <div className="text-xs text-zinc-500 italic truncate mb-1">{record.generated_subject}</div>
                      )}
                      <div className="flex items-center gap-2 text-zinc-400 text-sm">
                        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                        {record.company_email === 'not updated' && editingEmailId !== record.id ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); setEditingEmailId(record.id); setTempEmail(''); }}
                            className="text-amber-400 font-bold hover:text-amber-300 underline underline-offset-4 decoration-amber-500/30"
                          >
                            + Add Recipient Email
                          </button>
                        ) : editingEmailId === record.id ? (
                          <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                            <input
                              autoFocus
                              type="email"
                              value={tempEmail}
                              onChange={e => setTempEmail(e.target.value)}
                              placeholder="enter email..."
                              className="bg-zinc-800 border border-zinc-600 rounded px-2 py-0.5 text-xs text-white focus:outline-none focus:border-blue-500"
                            />
                            <button onClick={(e) => handleSaveEmail(record.id, e)} className="text-[10px] font-black uppercase text-emerald-400 hover:text-emerald-300">Save</button>
                            <button onClick={(e) => { e.stopPropagation(); setEditingEmailId(null); }} className="text-[10px] font-black uppercase text-zinc-500 hover:text-zinc-400">Cancel</button>
                          </div>
                        ) : (
                          <span className="truncate">{record.company_email}</span>
                        )}
                      </div>
                    </div>

                    {/* Dates */}
                    <div className="flex gap-4 text-xs text-zinc-500 shrink-0">
                      {(record.date_applied || record.timestamp) && (
                        <div className="flex flex-col items-end">
                          <span className="text-zinc-600 font-medium uppercase tracking-wider text-[9px]">Added</span>
                          <span className="text-zinc-300">{fmtDate(record.date_applied || record.timestamp)}</span>
                        </div>
                      )}
                      {record.followup_date && (
                        <div className="flex flex-col items-end">
                          <span className="text-zinc-600 font-medium uppercase tracking-wider text-[9px]">Follow-up</span>
                          <span className="text-zinc-300">{fmtDate(record.followup_date)}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Row 3: Unique application ID (follow-ups only) */}
                  {record.type === 'followup' && record.Unique_application_id && (
                    <div className="mt-2.5 flex items-center gap-2">
                      <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-600">App ID</span>
                      <code className="text-[10px] font-mono text-purple-400/70 bg-purple-500/5 border border-purple-500/10 px-2 py-0.5 rounded-md">
                        {record.Unique_application_id}
                      </code>
                    </div>
                  )}

                  {/* Row 4: Summary snippet & Feedback (follow-ups only) */}
                  {record.type === 'followup' && record.overall_summary && (
                    <div className="mt-2 border-t border-zinc-800/50 pt-2 flex flex-col gap-3">
                      <div className="text-xs text-zinc-500 italic line-clamp-2">
                        {record.overall_summary.split('\n').at(-1)}
                      </div>
                      <div onClick={e => e.stopPropagation()}>
                        <FollowupFeedbackWidget 
                          appId={record.Unique_application_id || String(record.id)}
                          summary={record.overall_summary}
                          context={record.context || ''}
                        />
                      </div>
                    </div>
                  )}

                  {/* Row 5: Action buttons */}
                  {!isTerminal && (
                    <div className="mt-4 flex items-center gap-2 border-t border-zinc-800/40 pt-4" onClick={e => e.stopPropagation()}>
                      <button
                        disabled={isLoading || record.company_email === 'not updated'}
                        onClick={(e) => handleApprove(record, e)}
                        className={`flex-[2] py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50
                          ${record.company_email === 'not updated'
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-500/70 cursor-not-allowed'
                            : 'bg-emerald-600/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-600 hover:text-white hover:border-emerald-600'}`}
                      >
                        {isLoading ? '…' : record.company_email === 'not updated' ? '⚠ Add Email to Approve' : '✓ Approve'}
                      </button>
                      <button
                        disabled={isLoading}
                        onClick={(e) => handleReject(record, e)}
                        className="flex-1 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-bold uppercase tracking-wider
                          hover:bg-red-600 hover:text-white hover:border-red-600 transition-all disabled:opacity-40"
                      >
                        {isLoading ? '…' : '✕ Reject'}
                      </button>
                      <button
                        disabled={isLoading}
                        onClick={(e) => handleDelete(record, e)}
                        title="Delete record permanently"
                        className="p-2 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 hover:border-red-500/30 transition-all"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
};

export default TrackingDashboard;