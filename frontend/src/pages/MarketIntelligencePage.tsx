import { useState, useEffect, useRef, useCallback } from 'react';
import MarketFeedbackWidget from '../component/MarketFeedbackWidget';



const API = '';
const PIPELINE_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

interface RiskAlert { rule_id: string; category: string; rule_name: string; severity: string; recommendation: string; triggered: boolean; condition: string; }
interface RiskData { generated_at: string; summary: { total_rules_evaluated: number; alerts_triggered: number; critical_alerts: number; high_alerts: number; medium_alerts: number; }; llm_strategic_analysis: string; triggered_alerts: RiskAlert[]; data_snapshot: Record<string, any>; }
interface WeatherCity { city: string; total_rain_mm: number; max_rain_chance_pct: number; max_temp_c: number; avg_temp_c: number; }
interface WeatherData { generated_at: string; crop_season: string; regional_stats: { sindh: { total_rain_mm: number; max_temp_c: number; heatwave_days_45plus: number; city_summaries: WeatherCity[]; }; punjab: { total_rain_mm: number; max_temp_c: number; heatwave_days_45plus: number; city_summaries: WeatherCity[]; }; }; weather_strategy: Record<string, any>; }

const SEV_COLOR: Record<string, string> = { CRITICAL: '#ff4444', HIGH: '#ff8c00', MEDIUM: '#f59e0b', LOW: '#22c55e', INFO: '#60a5fa' };
const SEV_BG: Record<string, string> = { CRITICAL: 'rgba(255,68,68,.13)', HIGH: 'rgba(255,140,0,.12)', MEDIUM: 'rgba(245,158,11,.12)', LOW: 'rgba(34,197,94,.10)', INFO: 'rgba(96,165,250,.10)' };

function fmt(iso: string) { try { return new Date(iso).toLocaleString(); } catch { return iso; } }
function parseLLM(raw: string) { try { return JSON.parse(raw); } catch { return null; } }

export default function MarketIntelligencePage() {
  const [risk, setRisk] = useState<RiskData | null>(null);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [pipeline, setPipeline] = useState<{ status: string; phase: string; log: string[] }>({ status: 'idle', phase: '', log: [] });
  const [countdown, setCountdown] = useState<number | null>(null); // Null until synced
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'alerts' | 'market' | 'weather' | 'log'>('alerts');
  const nextRunRef = useRef<number | null>(null); // Null until synced from backend
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Market Chat State
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'ai', content: string, feedbackGiven?: boolean, showFeedback?: boolean }[]>([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const [chatFeedbackText, setChatFeedbackText] = useState('');

  const load = useCallback(async () => {
    try {
      const [r, w] = await Promise.all([
        fetch(`${API}/api/stats/risk-factors`).then(x => x.json()).catch(() => null),
        fetch(`${API}/api/stats/weather-strategy`).then(x => x.json()).catch(() => null),
      ]);

      if (r && !r.error) setRisk(r);
      if (w && !w.error) setWeather(w);

      // Sync System Clock from Backend
      const { nextRunAt } = await fetch(`${API}/api/stats/next-run`).then(x => x.json()).catch(() => ({ nextRunAt: Date.now() + PIPELINE_INTERVAL_MS }));
      nextRunRef.current = nextRunAt;

    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  const triggerPipeline = useCallback(async () => {
    await fetch(`${API}/api/stats/run-pipeline`, { method: 'POST' });
    nextRunRef.current = Date.now() + PIPELINE_INTERVAL_MS;
    pollingRef.current && clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      const s = await fetch(`${API}/api/stats/pipeline-status`).then(x => x.json());
      setPipeline(s);
      if (s.status === 'done' || s.status === 'error') {
        clearInterval(pollingRef.current!);
        load();
      }
    }, 3000);
  }, [load]);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;

    const userMsg = chatInput;
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsChatLoading(true);

    try {
      const res = await fetch(`${API}/api/market/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMsg })
      });
      const data = await res.json();

      let answerText = "";
      if (typeof data.answer === 'string') {
        answerText = data.answer;
      } else if (data.answer && typeof data.answer === 'object') {
        // Handle JSON response { response: "..." } or error { error: "..." }
        answerText = data.answer.response || data.answer.error || JSON.stringify(data.answer);
      } else {
        answerText = "I'm sorry, I couldn't process that query.";
      }

      setChatMessages(prev => [...prev, { role: 'ai', content: answerText }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { role: 'ai', content: "Error connecting to the intelligence engine." }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const submitChatFeedback = async (index: number, type: 'good' | 'bad') => {
    const msg = chatMessages[index];
    const prevUserMsg = chatMessages[index - 1]?.content || '';

    try {
      await fetch('http://localhost:5050/api/feedback/market_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: type,
          user_input: prevUserMsg,
          agent_response: msg.content,
          user_comment: chatFeedbackText
        })
      });

      const newMessages = [...chatMessages];
      newMessages[index] = { ...msg, feedbackGiven: true, showFeedback: false };
      setChatMessages(newMessages);
      setChatFeedbackText('');
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages]);

  useEffect(() => {
    load();
    // Countdown tick
    const tick = setInterval(() => {
      if (nextRunRef.current === null) return;

      const left = nextRunRef.current - Date.now();
      setCountdown(Math.max(0, left));
      if (left <= 0) { triggerPipeline(); }
    }, 1000);
    return () => { clearInterval(tick); pollingRef.current && clearInterval(pollingRef.current); };
  }, [load, triggerPipeline]);

  const mm = String(Math.floor((countdown || 0) / 60000)).padStart(2, '0');
  const ss = String(Math.floor(((countdown || 0) % 60000) / 1000)).padStart(2, '0');

  const llm = risk ? parseLLM(risk.llm_strategic_analysis) : null;

  return (
    <div style={{ height: '100vh', overflowY: 'auto', background: '#050816', color: '#e2e8f0', fontFamily: "'Inter',sans-serif" }}>
      {/* Header */}
      <div style={{ background: 'linear-gradient(135deg,#0f1729 0%,#1a1040 100%)', borderBottom: '1px solid rgba(99,102,241,.3)', padding: '20px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, background: 'linear-gradient(90deg,#818cf8,#c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            TEXBASE Market Intelligence
          </h1>
          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 4 }}>
            {risk && <>Last updated: {fmt(risk.generated_at)}</>}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <button
            onClick={() => {
              window.history.pushState({}, '', '/dashboard');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '8px 16px', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.1)'; (e.currentTarget as HTMLButtonElement).style.color = '#fff'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.05)'; (e.currentTarget as HTMLButtonElement).style.color = '#94a3b8'; }}
          >
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
            Dashboard
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* Countdown */}
            <div style={{ textAlign: 'center', background: 'rgba(99,102,241,.15)', border: '1px solid rgba(99,102,241,.3)', borderRadius: 12, padding: '8px 20px', minWidth: 120 }}>
              <div style={{ fontSize: '0.65rem', color: '#818cf8', letterSpacing: 2, textTransform: 'uppercase' }}>Next Refresh</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: (countdown || 0) < 300000 ? '#f87171' : '#c4b5fd' }}>
                {countdown !== null ? `${mm}:${ss}` : '--:--'}
              </div>
            </div>
            {/* Pipeline status */}
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={triggerPipeline} style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', border: 'none', borderRadius: 10, padding: '10px 18px', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '0.85rem' }}>
                Run Now
              </button>
            </div>
            <div style={{ fontSize: '0.75rem', padding: '6px 12px', borderRadius: 8, background: pipeline.status === 'running' ? 'rgba(251,191,36,.15)' : pipeline.status === 'done' ? 'rgba(34,197,94,.15)' : 'rgba(100,116,139,.15)', color: pipeline.status === 'running' ? '#fbbf24' : pipeline.status === 'done' ? '#4ade80' : '#94a3b8', border: `1px solid ${pipeline.status === 'running' ? 'rgba(251,191,36,.4)' : pipeline.status === 'done' ? 'rgba(34,197,94,.4)' : 'rgba(100,116,139,.3)'}` }}>
              {pipeline.status === 'running' ? `In Progress: ${pipeline.phase}…` : pipeline.status === 'done' ? 'Success' : 'Idle'}
            </div>
          </div>
        </div>
      </div>      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 100 }}>
          <div style={{ width: 40, height: 40, border: '3px solid rgba(99,102,241,.3)', borderTopColor: '#818cf8', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <div style={{ marginTop: 20, color: '#64748b', fontWeight: 500 }}>Analyzing market intelligence...</div>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {!loading && !risk && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 100, textAlign: 'center' }}>
          <h2 style={{ color: '#fff', margin: '0 0 10px' }}>No Intelligence Data Found</h2>
          <p style={{ color: '#64748b', maxWidth: 400, margin: '0 0 30px' }}>The automated market intelligence pipeline hasn't been run yet. Click the button below to start the initial analysis.</p>
          <button
            onClick={triggerPipeline}
            style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', border: 'none', borderRadius: 10, padding: '12px 30px', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: '1rem', boxShadow: '0 10px 20px rgba(99,102,241,0.2)' }}
          >
            Start Initial Analysis
          </button>
        </div>
      )}

      {!loading && risk && (
        <>
          {/* Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 16, padding: '24px 32px 0' }}>
            {[
              { label: 'Rules Evaluated', val: risk?.summary?.total_rules_evaluated || 0, color: '#818cf8' },
              { label: 'Triggered Alerts', val: risk?.summary?.alerts_triggered || 0, color: '#60a5fa' },
              { label: 'Critical', val: risk?.summary?.critical_alerts || 0, color: '#f87171' },
              { label: 'High', val: risk?.summary?.high_alerts || 0, color: '#fb923c' },
              { label: 'Medium', val: risk?.summary?.medium_alerts || 0, color: '#fbbf24' },
            ].map(c => (
              <div key={c.label} style={{ background: 'rgba(15,23,42,.8)', border: '1px solid rgba(99,102,241,.2)', borderRadius: 12, padding: '16px 20px' }}>
                <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: 1 }}>{c.label}</div>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: c.color, marginTop: 4 }}>{c.val}</div>
              </div>
            ))}
          </div>

          {/* Compound Risk Score */}
          {llm?.compound_risk_score != null && (
            <div style={{ margin: '20px 32px 0', background: 'linear-gradient(135deg,rgba(239,68,68,.15),rgba(168,85,247,.15))', border: '1px solid rgba(239,68,68,.3)', borderRadius: 14, padding: '16px 24px', display: 'flex', alignItems: 'center', gap: 20 }}>
              <div style={{ fontSize: '3rem', fontWeight: 800, color: llm.compound_risk_score >= 8 ? '#f87171' : llm.compound_risk_score >= 5 ? '#fb923c' : '#4ade80' }}>{llm.compound_risk_score}/10</div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#e2e8f0' }}>Compound Risk Score</div>
                <div style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: 4, maxWidth: 700 }}>{llm?.market_overview || ''}</div>
              </div>
            </div>
          )}
          {risk && (
            <div className="px-8">
              <MarketFeedbackWidget
                parameterName="Market Strategic Overview"
                predictionSummary={risk.llm_strategic_analysis.slice(0, 200)}
                fullResponse={risk.llm_strategic_analysis}
              />
            </div>
          )}



          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4, padding: '20px 32px 0' }}>
            {(['alerts', 'market', 'weather', 'log'] as const).map(t => (
              <button key={t} onClick={() => setTab(t)} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem', transition: 'all .2s', background: tab === t ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : 'rgba(30,41,59,.8)', color: tab === t ? '#fff' : '#64748b' }}>
                {t === 'alerts' ? 'Alerts' : t === 'market' ? 'Market Data' : t === 'weather' ? 'Weather' : 'Pipeline Log'}
              </button>
            ))}
          </div>

          <div style={{ padding: '20px 32px 40px' }}>

            {/* ── ALERTS TAB ── */}
            {tab === 'alerts' && (
              <div>
                {/* LLM Dept Actions */}
                {llm && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
                    {[['Cotton Dept', 'cotton_dept'], ['Yarn Dept', 'yarn_dept'], ['Chemicals Dept', 'chemicals_dept'], ['Forex Dept', 'forex_dept']].map(([label, key]) => (
                      <div key={key} style={{ background: 'rgba(15,23,42,.8)', border: '1px solid rgba(99,102,241,.2)', borderRadius: 12, padding: 16 }}>
                        <div style={{ color: '#818cf8', fontWeight: 700, marginBottom: 6, fontSize: '0.85rem' }}>{label}</div>
                        <div style={{ color: '#cbd5e1', fontSize: '0.85rem', lineHeight: 1.6 }}>{llm[key] || '—'}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 14-day Watchlist */}
                {llm?.['14_day_watchlist'] && (
                  <div style={{ marginBottom: 24, background: 'rgba(15,23,42,.8)', border: '1px solid rgba(251,191,36,.25)', borderRadius: 12, padding: 16 }}>
                    <div style={{ color: '#fbbf24', fontWeight: 700, marginBottom: 10 }}>14-Day Watchlist</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {llm['14_day_watchlist'].map((item: string) => (
                        <span key={item} style={{ background: 'rgba(251,191,36,.12)', border: '1px solid rgba(251,191,36,.3)', borderRadius: 20, padding: '4px 12px', fontSize: '0.75rem', color: '#fde68a' }}>{item}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Critical Actions */}
                {llm?.critical_actions && (
                  <div style={{ marginBottom: 24, background: 'rgba(15,23,42,.8)', border: '1px solid rgba(239,68,68,.3)', borderRadius: 12, padding: 16 }}>
                    <div style={{ color: '#f87171', fontWeight: 700, marginBottom: 10 }}>Critical Actions Now</div>
                    {llm.critical_actions.map((a: string, i: number) => (
                      <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8 }}>
                        <span style={{ color: '#f87171', fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
                        <span style={{ color: '#fca5a5', fontSize: '0.85rem' }}>{a}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Alert Cards by Category */}
                {Object.entries(
                  (risk.triggered_alerts || []).reduce((acc: Record<string, RiskAlert[]>, a) => { (acc[a.category] ||= []).push(a); return acc; }, {})
                ).map(([cat, alerts]) => (
                  <div key={cat} style={{ marginBottom: 20 }}>
                    <h3 style={{ margin: '0 0 10px', color: '#94a3b8', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: 2 }}>{cat}</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(340px,1fr))', gap: 12 }}>
                      {(alerts as RiskAlert[]).map(a => (
                        <div key={a.rule_id} style={{ background: SEV_BG[a.severity] || 'rgba(15,23,42,.8)', border: `1px solid ${SEV_COLOR[a.severity] || '#334155'}44`, borderLeft: `3px solid ${SEV_COLOR[a.severity] || '#334155'}`, borderRadius: 10, padding: 14 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#e2e8f0' }}>{a.rule_name}</span>
                            <span style={{ fontSize: '0.65rem', fontWeight: 700, color: SEV_COLOR[a.severity], background: `${SEV_COLOR[a.severity]}20`, padding: '2px 8px', borderRadius: 6, flexShrink: 0, marginLeft: 8 }}>{a.severity}</span>
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: 6, fontFamily: 'monospace' }}>{a.condition}</div>
                          <div style={{ fontSize: '0.82rem', color: SEV_COLOR[a.severity] || '#94a3b8' }}>{a.recommendation}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── MARKET DATA TAB ── */}
            {tab === 'market' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 12 }}>
                {Object.entries(risk.data_snapshot || {}).filter(([, v]) => typeof v === 'number' || typeof v === 'string').map(([k, v]) => (
                  <div key={k} style={{ background: 'rgba(15,23,42,.8)', border: '1px solid rgba(99,102,241,.15)', borderRadius: 10, padding: '12px 16px' }}>
                    <div style={{ fontSize: '0.68rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>{k.replace(/_/g, ' ')}</div>
                    <div style={{ fontSize: '1.05rem', fontWeight: 600, color: '#c4b5fd' }}>{typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(v)}</div>
                  </div>
                ))}
              </div>
            )}

            {/* WEATHER TAB */}
            {tab === 'weather' && weather && (
              <div>
                <div style={{ background: 'rgba(15,23,42,.8)', border: '1px solid rgba(56,189,248,.3)', borderRadius: 12, padding: '12px 20px', marginBottom: 20, display: 'flex', gap: 24 }}>
                  <span style={{ color: '#38bdf8', fontWeight: 700 }}>{weather.crop_season}</span>
                  <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Updated: {fmt(weather.generated_at)}</span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
                  {(['sindh', 'punjab'] as const).map(region => {
                    const r = weather.regional_stats[region];
                    return (
                      <div key={region} style={{ background: 'rgba(15,23,42,.8)', border: '1px solid rgba(56,189,248,.2)', borderRadius: 12, padding: 20 }}>
                        <h3 style={{ margin: '0 0 16px', color: '#38bdf8', textTransform: 'capitalize' }}>{region}</h3>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
                          {[['Total Rain', `${r.total_rain_mm}mm`], ['Max Temp', `${r.max_temp_c}°C`], ['Heatwave Days', `${r.heatwave_days_45plus} days ≥45°C`]].map(([l, v]) => (
                            <div key={l} style={{ background: 'rgba(56,189,248,.08)', borderRadius: 8, padding: '10px 14px' }}>
                              <div style={{ fontSize: '0.68rem', color: '#64748b' }}>{l}</div>
                              <div style={{ fontWeight: 700, color: '#7dd3fc', fontSize: '1rem' }}>{v}</div>
                            </div>
                          ))}
                        </div>
                        {r.city_summaries?.map((c: WeatherCity) => (
                          <div key={c.city} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(99,102,241,.1)', fontSize: '0.8rem' }}>
                            <span style={{ color: '#94a3b8' }}>{c.city}</span>
                            <span style={{ color: '#fbbf24' }}>{c.max_temp_c}°C</span>
                            <span style={{ color: '#60a5fa' }}>{c.total_rain_mm}mm</span>
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>

                {/* Weather Strategy */}
                {weather.weather_strategy && !weather.weather_strategy.raw_llm_response && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    {[['Crop Risk', weather.weather_strategy.crop_risk_assessment], ['Procurement', weather.weather_strategy.procurement_strategy], ['Operational', weather.weather_strategy.operational_impacts], ['Ginning Quality', weather.weather_strategy.ginning_quality_risk]].filter(([, v]) => v).map(([l, v]) => (
                      <div key={l as string} style={{ background: 'rgba(15,23,42,.8)', border: '1px solid rgba(56,189,248,.2)', borderRadius: 10, padding: 16 }}>
                        <div style={{ color: '#38bdf8', fontWeight: 700, marginBottom: 8, fontSize: '0.85rem' }}>{l as string}</div>
                        <div style={{ color: '#cbd5e1', fontSize: '0.82rem', lineHeight: 1.6 }}>{v as string}</div>
                      </div>
                    ))}
                    {weather.weather_strategy.logistics_advisory && (
                      <div style={{ background: 'rgba(15,23,42,.8)', border: '1px solid rgba(56,189,248,.2)', borderRadius: 10, padding: 16, gridColumn: '1/-1' }}>
                        <div style={{ color: '#38bdf8', fontWeight: 700, marginBottom: 10, fontSize: '0.85rem' }}>Logistics Advisory</div>
                        {weather.weather_strategy.logistics_advisory.map((l: string, i: number) => (
                          <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6, fontSize: '0.82rem', color: '#94a3b8' }}>
                            <span style={{ color: '#38bdf8' }}>›</span>{l}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── PIPELINE LOG TAB ── */}
            {tab === 'log' && (
              <div style={{ background: '#020817', border: '1px solid rgba(99,102,241,.2)', borderRadius: 12, padding: 20, fontFamily: 'monospace', fontSize: '0.78rem', color: '#4ade80', maxHeight: 500, overflowY: 'auto' }}>
                {pipeline.log.length === 0 && <span style={{ color: '#64748b' }}>No pipeline logs yet. Click "Run Now" to start.</span>}
                {pipeline.log.map((l, i) => <div key={i} style={{ marginBottom: 3, color: l.includes('err') || l.includes('FAILED') ? '#f87171' : l.includes('✅') ? '#4ade80' : '#94a3b8' }}>{l}</div>)}
              </div>
            )}
          </div>
        </>
      )}

      {/* Floating RAG Chat Widget */}
      <div style={{ position: 'fixed', bottom: 32, right: 32, zIndex: 1000 }}>
        {chatOpen && (
          <div style={{
            width: 380, height: 500, background: '#0f172a', border: '1px solid rgba(99,102,241,0.4)',
            borderRadius: 20, display: 'flex', flexDirection: 'column', overflow: 'hidden',
            boxShadow: '0 20px 50px rgba(0,0,0,0.5)', marginBottom: 16
          }}>
            <div style={{ padding: '16px 20px', background: 'linear-gradient(90deg, #1e293b, #0f172a)', borderBottom: '1px solid rgba(99,102,241,0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 10px #10b981' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#fff', letterSpacing: 1 }}>MARKET ANALYST RAG</span>
              </div>
              <button onClick={() => setChatOpen(false)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}>✕</button>
            </div>

            <div ref={chatScrollRef} style={{ flexGrow: 1, padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {chatMessages.length === 0 && (
                <div style={{ textAlign: 'center', marginTop: 40, color: '#475569' }}>
                  <div style={{ fontSize: '2rem', marginBottom: 10 }}></div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>Ask anything about cotton prices, <br />risk factors, or weather impacts.</div>
                </div>
              )}
              {chatMessages.map((m, i) => (
                <div key={i} style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%', display: 'flex', flexDirection: 'column', gap: 4
                }}>
                  <div style={{
                    padding: '10px 14px', borderRadius: 14,
                    background: m.role === 'user' ? '#4f46e5' : 'rgba(255,255,255,0.05)',
                    border: m.role === 'user' ? 'none' : '1px solid rgba(255,255,255,0.1)',
                    color: m.role === 'user' ? '#fff' : '#cbd5e1',
                    fontSize: '0.85rem', lineHeight: 1.5, whiteSpace: 'pre-wrap'
                  }}>
                    {m.content}
                  </div>

                  {m.role === 'ai' && !m.feedbackGiven && !m.showFeedback && (
                    <div style={{ display: 'flex', gap: 8, paddingLeft: 4 }}>
                      <button onClick={() => setChatMessages(prev => prev.map((msg, idx) => idx === i ? { ...msg, showFeedback: true } : msg))} style={{ background: 'none', border: 'none', color: '#64748b', fontSize: '10px', cursor: 'pointer', padding: 0 }}>Feedback?</button>
                    </div>
                  )}

                  {m.role === 'ai' && m.showFeedback && (
                    <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 10, padding: 10, marginTop: 4, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <textarea
                        value={chatFeedbackText}
                        onChange={(e) => setChatFeedbackText(e.target.value)}
                        placeholder="What did you like or dislike?"
                        style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, color: '#fff', fontSize: '11px', padding: 6, outline: 'none', minHeight: 60 }}
                      />
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => submitChatFeedback(i, 'good')} style={{ flex: 1, background: '#10b98120', border: '1px solid #10b98140', color: '#10b981', borderRadius: 6, fontSize: '10px', padding: '4px 0', cursor: 'pointer', fontWeight: 'bold' }}>👍 Good</button>
                        <button onClick={() => submitChatFeedback(i, 'bad')} style={{ flex: 1, background: '#ef444420', border: '1px solid #ef444440', color: '#ef4444', borderRadius: 6, fontSize: '10px', padding: '4px 0', cursor: 'pointer', fontWeight: 'bold' }}>👎 Bad</button>
                      </div>
                    </div>
                  )}

                  {m.role === 'ai' && m.feedbackGiven && (
                    <div style={{ fontSize: '10px', color: '#10b981', paddingLeft: 4, fontStyle: 'italic' }}>Feedback recorded ✓</div>
                  )}
                </div>
              ))}
              {isChatLoading && (
                <div style={{ alignSelf: 'flex-start', padding: '10px 14px', borderRadius: 14, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#64748b', animation: 'pulse 1s infinite' }} />
                    <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#64748b', animation: 'pulse 1s infinite 0.2s' }} />
                    <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#64748b', animation: 'pulse 1s infinite 0.4s' }} />
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={handleChatSubmit} style={{ padding: 16, background: 'rgba(255,255,255,0.02)', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask market intelligence..."
                style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 10, padding: '10px 14px', color: '#fff', fontSize: '0.85rem', outline: 'none' }}
              />
            </form>
          </div>
        )}

        <button
          onClick={() => setChatOpen(!chatOpen)}
          style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', color: '#fff', cursor: 'pointer',
            boxShadow: '0 8px 32px rgba(99,102,241,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'transform 0.2s'
          }}
          onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
        >
          {chatOpen ? '✕' : (
            <svg width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          )}
        </button>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
