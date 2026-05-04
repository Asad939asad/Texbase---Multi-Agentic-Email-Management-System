import { useState, useEffect } from 'react';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import EmailEditor from './pages/email_editor';
import MarketIntelligencePage from './pages/MarketIntelligencePage';
import POQuotationPage from './pages/POQuotationPage';

type Page = 'loading' | 'login' | 'dashboard' | 'review' | 'editor' | 'sending-review' | 'follow-ups' | 'intel' | 'inbox' | 'po-quote';
import TrackingDashboard from './pages/email_review';
import SendingReviewDashboard from './pages/Sending_review';
import SentPipelinePage from './pages/follow_up';
import InboxPage from './pages/InboxPage';
import LightRays from './component/LightRays';

interface UserInfo {
  name: string;
  email: string;
}

export default function App() {
  const [page, setPage] = useState<Page>('loading');
  const [user, setUser] = useState<UserInfo | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const isOAuth = params.get('google_connected') === 'true';

    if (isOAuth) {
      // ── Coming back from Google OAuth ──────────────────────────────────
      const u: UserInfo = {
        name: decodeURIComponent(params.get('name') ?? ''),
        email: decodeURIComponent(params.get('email') ?? ''),
      };
      const targetPage = params.get('page') === 'dashboard' ? 'dashboard' : 'dashboard';

      window.history.replaceState({}, '', `/${targetPage}`);
      setUser(u);
      setPage(targetPage);

    } else {
      // ── Verify Session and Registration ────────────────────────────────
      fetch('http://localhost:8000/api/auth/session')
        .then(r => r.ok ? r.json() : null)
        .then((data: UserInfo | null) => {
          if (data?.email) {
            // Session exists, let's verify if they are in the DB
            fetch(`http://localhost:8000/api/auth/check-registered?email=${encodeURIComponent(data.email)}`)
              .then(r => r.ok ? r.json() : { registered: false })
              .then((result: { registered: boolean }) => {
                const currentPath = window.location.pathname;
                let finalTarget: Page = result.registered ? 'dashboard' : 'dashboard';

                if (result.registered && currentPath === '/review') {
                  finalTarget = 'review';
                }
                if (result.registered && currentPath === '/editor') {
                  finalTarget = 'editor';
                }
                if (result.registered && currentPath === '/sending-review') {
                  finalTarget = 'sending-review';
                }
                if (result.registered && currentPath === '/follow-ups') {
                  finalTarget = 'follow-ups';
                }
                if (result.registered && currentPath === '/follow-ups') {
                  finalTarget = 'follow-ups';
                }
                if (result.registered && currentPath === '/market-intelligence') {
                  finalTarget = 'intel';
                }
                if (result.registered && currentPath === '/inbox') {
                  finalTarget = 'inbox';
                }
                if (result.registered && currentPath === '/po-quote') {
                  finalTarget = 'po-quote';
                }

                if (currentPath !== `/${finalTarget}`) {
                  window.history.replaceState({}, '', `/${finalTarget}`);
                }

                setUser(data);
                setPage(finalTarget);
              })
              .catch(() => {
                setUser(data);
                if (window.location.pathname !== '/dashboard') {
                  window.history.replaceState({}, '', '/dashboard');
                }
                setPage('dashboard');
              });
          } else {
            // No session, go to login
            if (window.location.pathname !== '/') {
              window.history.replaceState({}, '', '/');
            }
            setPage('login');
          }
        })
        .catch(() => {
          if (window.location.pathname !== '/') {
            window.history.replaceState({}, '', '/');
          }
          setPage('login');
        });
    }

    // Handle browser back/forward navigation
    const handlePopState = () => {
      const path = window.location.pathname;
      if (path === '/review') setPage('review');
      else if (path === '/sending-review') setPage('sending-review');
      else if (path === '/follow-ups') setPage('follow-ups');
      else if (path === '/editor') setPage('editor');
      else if (path === '/dashboard') setPage('dashboard');
      else if (path === '/intel' || path === '/market-intelligence') setPage('intel');
      else if (path === '/inbox') setPage('inbox');
      else if (path === '/po-quote') setPage('po-quote');
      else setPage('login');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [prevActive, setPrevActive] = useState(false);

  useEffect(() => {
    const checkStatus = () => {
      fetch(`http://${window.location.hostname}:8000/api/pipeline/status`)
        .then(r => r.json())
        .then(data => {
          setIsPipelineRunning(data.active);
          if (prevActive && !data.active) {
            // It just finished
            if (data.lastExitCode !== 0 && data.lastExitCode !== null) {
              alert(`❌ Pipeline failed with exit code ${data.lastExitCode}. Check backend logs.`);
            } else if (data.lastExitCode === 0) {
              alert('✅ Outreach Pipeline Completed Successfully!');
            }
          }
          setPrevActive(data.active);
        })
        .catch(() => { });
    };
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, [prevActive]);

  const handleLogout = async () => {
    try {
      await fetch('http://localhost:8000/api/auth/logout');
    } catch (e) {
      console.error(e);
    }
    setUser(null);
    setPage('login');
    window.history.replaceState({}, '', '/');
  };

  if (page === 'loading') return <Spinner />;

  // These pages are rendered with the App Shell (Nav + Background)
  const renderContent = () => {
    if (page === 'editor') {
      const editId = new URLSearchParams(window.location.search).get('id');
      return <EmailEditor id={editId!} onLogout={handleLogout} />;
    }
    if (page === 'review') return <TrackingDashboard />;
    if (page === 'sending-review') return <SendingReviewDashboard />;
    if (page === 'follow-ups') return <SentPipelinePage />;
    if (page === 'intel') return <MarketIntelligencePage />;
    if (page === 'inbox') return <InboxPage />;
    if (page === 'po-quote') return <POQuotationPage />;
    if (page === 'dashboard') return <DashboardPage user={user} />;
    return <LoginPage onLogout={handleLogout} />;
  };

  // If it's login or loading, we don't show the full shell (optional, but cleaner)
  if (page === 'login') return <LoginPage onLogout={handleLogout} />;

  return (
    <main className="relative w-full min-h-screen overflow-y-auto overflow-x-hidden bg-zinc-950 text-white flex flex-col">
      {/* 1. Global Background Layer */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <LightRays />
      </div>

      {/* 2. Global Navigation (Dashboard Only) */}
      {page === 'dashboard' && (
        <nav className="fixed top-0 left-0 w-full z-20 px-6 py-3 flex items-center justify-between bg-zinc-950/20 backdrop-blur-md border-b border-white/5">
          <div
            onClick={() => { window.history.pushState({}, '', '/dashboard'); window.dispatchEvent(new PopStateEvent('popstate')); }}
            className="text-2xl font-black tracking-tighter text-white flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-9 h-9 rounded bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-110 transition-transform">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="text-zinc-200 group-hover:text-white transition-colors font-extrabold uppercase">TEXTILE NEXUS<span className="text-indigo-500">.</span></span>
          </div>

          <div className="absolute left-1/2 -translate-x-1/2 flex gap-10 text-[15px] uppercase tracking-[0.25em] font-semibold text-white hidden lg:flex">
            <button onClick={() => { window.history.pushState({}, '', '/dashboard'); window.dispatchEvent(new PopStateEvent('popstate')); }} className="hover:text-white hover:tracking-[0.3em] transition-all duration-300">Dashboard</button>
            <button onClick={() => { window.history.pushState({}, '', '/inbox'); window.dispatchEvent(new PopStateEvent('popstate')); }} className="hover:text-white hover:tracking-[0.3em] transition-all duration-300">Inbox</button>
            <button onClick={() => { window.history.pushState({}, '', '/review'); window.dispatchEvent(new PopStateEvent('popstate')); }} className="hover:text-white hover:tracking-[0.3em] transition-all duration-300">Pipeline</button>
            <button onClick={() => { window.history.pushState({}, '', '/intel'); window.dispatchEvent(new PopStateEvent('popstate')); }} className="hover:text-white hover:tracking-[0.3em] transition-all duration-300">Intelligence</button>
            <button onClick={() => { window.history.pushState({}, '', '/po-quote'); window.dispatchEvent(new PopStateEvent('popstate')); }} className="hover:text-white hover:tracking-[0.3em] transition-all duration-300">PO-Quotes</button>
          </div>

          <div className="flex items-center gap-4">
            <a
              href="http://localhost:3001"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] font-black text-white/70 hover:text-white uppercase tracking-wider bg-white/5 px-5 py-2 rounded-full border border-white/10 hover:border-white/20 transition-all duration-300"
            >
              MANAGEMENT APP
            </a>

            <button
              disabled={isPipelineRunning}
              onClick={async () => {
                console.log("🖱️ Triggering Outreach Pipeline...");
                try {
                  const hostname = window.location.hostname;
                  const r = await fetch(`http://${hostname}:8000/api/pipeline/run-excel`, { method: 'POST' });
                  if (r.ok) {
                    console.log("✅ Pipeline request accepted by server");
                    setIsPipelineRunning(true);
                    console.log("🚀 Outreach Pipeline Started in background!");
                  } else {
                    const err = await r.json();
                    alert(`❌ Error: ${err.error || r.status}`);
                  }
                } catch (e) {
                  console.error("❌ Network error:", e);
                  alert('❌ Failed to connect to backend.');
                }
              }}
              className={`text-[12px] font-black text-white uppercase tracking-widest px-6 py-2.5 rounded-full transition-all duration-300 border
                ${isPipelineRunning 
                  ? 'bg-zinc-800 border-zinc-700 text-zinc-500 cursor-not-allowed opacity-70' 
                  : 'bg-gradient-to-r from-indigo-600 to-purple-600 shadow-[0_0_20px_rgba(168,85,247,0.3)] hover:shadow-[0_0_30px_rgba(168,85,247,0.5)] hover:scale-105 border-white/10'}`}
            >
              {isPipelineRunning ? (
                <span className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
                  PIPELINE RUNNING...
                </span>
              ) : 'TRIGGER EMAIL'}
            </button>

            {user && (
              <div className="flex items-center gap-3 bg-white/5 px-4 py-2 rounded-full border border-white/5 hover:border-white/10 transition-colors ml-2">
                <div className="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center text-[13px] font-bold shadow-lg shadow-indigo-500/20">
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <span className="text-sm font-bold text-zinc-200 hidden sm:block">{user.name.split(' ')[0]}</span>
              </div>
            )}
            {user && (
              <button
                onClick={handleLogout}
                className="text-[11px] font-bold text-zinc-500 hover:text-red-400 uppercase tracking-widest transition-colors ml-2"
              >
                LOGOUT
              </button>
            )}
          </div>
        </nav>
      )}

      {/* 3. Page Content */}
      <div className={`relative z-10 flex-grow ${page === 'dashboard' ? 'pt-20' : ''}`}>
        {renderContent()}
      </div>
    </main>
  );
}

function Spinner() {
  return (
    <div style={{ position: 'fixed', inset: 0, background: '#03010f', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{
        width: '32px', height: '32px', borderRadius: '50%',
        border: '3px solid rgba(99,102,241,0.3)',
        borderTopColor: '#818cf8',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
