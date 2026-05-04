import React, { useState, useEffect } from 'react';

export interface TrackingRecord {
  id: number;
  body_json: string;
  timestamp: string;
  followup_date: string;
  status: string;
  company_name: string;
  generated_subject: string;
  company_email: string;
}

const TrackingDashboard: React.FC = () => {
  const [records, setRecords] = useState<TrackingRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [editingEmailId, setEditingEmailId] = useState<number | null>(null);
  const [tempEmail, setTempEmail] = useState('');
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchAll = () => {
    setLoading(true);
    fetch('http://localhost:8000/api/tracking_ready_to_send')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch');
        return res.json();
      })
      .then((data) => {
        setRecords(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching data:", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const updateMetadata = async (id: number, field: string, value: string) => {
    const res = await fetch(`http://localhost:8000/api/tracking/${id}/metadata`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ field, value, dbType: 'ready' }),
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

  const handleLogout = async () => {
    try {
      await fetch('http://localhost:8000/api/auth/logout');
    } catch (e) {
      console.error(e);
    }
    window.location.href = '/';
  };

  const getStatusColor = (status: string, email: string) => {
    if (email === 'not updated') return 'bg-red-500/10 text-red-400 border-red-500/30 shadow-red-500/10';
    const s = status.toLowerCase();
    if (s.includes('ready')) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 shadow-emerald-500/10';
    if (s.includes('sent')) return 'bg-blue-500/10 text-blue-400 border-blue-500/20 shadow-blue-500/10';
    return 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20 shadow-zinc-500/10';
  };

  const fmtDate = (d?: string) => {
    if (!d) return '—';
    try {
      const iso = d.includes(' ') ? d.replace(' ', 'T') : d;
      return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch { return d; }
  };

  return (
    <main className="min-h-screen w-full overflow-x-hidden bg-zinc-950 text-zinc-100 font-sans selection:bg-blue-500/30">
      <div className="fixed inset-0 z-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-zinc-900 via-zinc-950 to-black pointer-events-none" />

      {toast && (
        <div className={`fixed top-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm font-semibold shadow-2xl border transition-all
          ${toast.ok ? 'bg-zinc-900 border-emerald-500/40 text-emerald-300' : 'bg-zinc-900 border-red-500/40 text-red-300'}`}>
          {toast.msg}
        </div>
      )}

      <nav className="relative z-20 w-full px-8 py-5 border-b border-zinc-800/50 bg-zinc-950/80 backdrop-blur-md flex flex-col sm:flex-row justify-between items-center gap-4">
        <h1 className="text-xl font-black tracking-widest bg-gradient-to-r from-emerald-400 to-cyan-500 bg-clip-text text-transparent">
          READY TO SEND <span className="text-blue-500">.</span>
        </h1>
        <div className="flex items-center gap-6">
          <div className="text-sm font-medium text-zinc-400">
            Queue Size: <span className="text-white font-bold bg-zinc-800 px-2 py-0.5 rounded-md ml-1">{records.length}</span>
          </div>
          <button
            onClick={() => { window.history.pushState({}, '', '/review'); window.dispatchEvent(new PopStateEvent('popstate')); }}
            className="text-sm font-bold text-zinc-300 hover:text-white transition-all border border-zinc-600/50 px-4 py-1.5 rounded-lg bg-zinc-800/60 hover:bg-zinc-700/60"
          >
            ← Review Portal
          </button>
          <button
            onClick={handleLogout}
            className="text-sm font-bold text-red-400 hover:text-red-300 transition-all border border-red-500/30 px-4 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20"
          >
            Logout
          </button>
        </div>
      </nav>

      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-16 pb-24">
        <div className="relative z-20 mb-10 max-w-2xl mx-auto text-center md:text-left md:mx-0">
          <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-3 drop-shadow-md text-white">
            Send Queue
          </h2>
          <p className="text-zinc-400 text-base md:text-lg drop-shadow">
            Emails in this queue are approved and will be sent automatically by the background agent.
          </p>
        </div>

        <div className="w-full relative overflow-hidden px-4 md:px-0">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="text-zinc-500 animate-pulse font-medium text-lg">Accessing outbox...</div>
            </div>
          ) : records.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 border border-dashed border-zinc-800 rounded-2xl bg-zinc-900/20">
              <span className="text-2xl mb-2">📩</span>
              <div className="text-zinc-500 font-medium">Your outbox is currently empty.</div>
            </div>
          ) : (
            <div className="flex flex-col items-center w-full my-6">
              <div className="w-full flex flex-col items-center gap-4 max-w-3xl mx-auto pb-12">
                {records.map((record) => (
                  <div
                    key={record.id}
                    className="w-full group flex flex-col md:flex-row items-start md:items-center justify-between p-4 md:p-5 bg-zinc-900/60 backdrop-blur-xl border border-zinc-700/80 rounded-xl hover:bg-zinc-800/80 hover:border-zinc-500 transition-all duration-200 shadow-lg"
                  >
                    <div className="flex flex-col mb-4 md:mb-0 w-full md:w-1/2">
                      <h3 className="text-lg md:text-xl font-bold text-zinc-100 mb-0.5 truncate group-hover:text-emerald-400 transition-colors">
                        {record.company_name}
                      </h3>
                      <div className="text-xs text-zinc-500 italic truncate mb-2">{record.generated_subject}</div>
                      <div className="flex items-center gap-2 text-zinc-400 text-sm">
                        <svg className="w-4 h-4 text-zinc-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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

                    <div className="flex flex-col md:flex-row items-start md:items-center justify-end gap-6 w-full md:w-1/2">
                      <div className="flex flex-row md:flex-col gap-4 md:gap-1 text-sm text-zinc-500 w-full md:w-auto">
                        <div className="flex items-center gap-2 w-full md:w-auto md:justify-end">
                          <span className="text-zinc-600 font-medium uppercase tracking-wider text-[9px]">Approved</span>
                          <span className="text-zinc-300">{fmtDate(record.timestamp)}</span>
                        </div>
                        <div className="flex items-center gap-2 w-full md:w-auto md:justify-end">
                          <span className="text-zinc-600 font-medium uppercase tracking-wider text-[9px]">Scheduled</span>
                          <span className="text-zinc-300">{fmtDate(record.followup_date)}</span>
                        </div>
                      </div>

                      <div className={`shrink-0 px-3 py-1 rounded-md border text-[11px] font-bold uppercase tracking-wider shadow-sm ${getStatusColor(record.status, record.company_email)}`}>
                        {record.company_email === 'not updated' ? 'MISSING EMAIL' : record.status}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
};

export default TrackingDashboard;