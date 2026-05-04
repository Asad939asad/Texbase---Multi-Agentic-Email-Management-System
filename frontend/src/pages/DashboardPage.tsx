import React from 'react';

interface PageProps {
  user?: { name: string; email: string } | null;
}

const DashboardPage: React.FC<PageProps> = ({ user }) => {

  return (
    <div className="flex flex-col items-center justify-center w-full px-4 pt-10 pb-20">
        <div className="text-center mb-8 shrink-0">
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl mb-3 drop-shadow-lg bg-clip-text text-transparent bg-gradient-to-r from-white to-zinc-400">
            Welcome back{user ? `, ${user.name.split(' ')[0]}` : ''}
          </h1>
          <p className="max-w-2xl mx-auto text-base text-zinc-400 drop-shadow-md">
            Manage your recruitment pipeline, process incoming applications, and track candidate progress through the agentic workflow.
          </p>
        </div>

        {/* Premium Grid Layout */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 w-full max-w-7xl mx-auto mt-6">
          
          <DashboardCard
            title="Inbox"
            description="View direct replies to your sent emails and automated response threads."
            buttonText="Open Inbox"
            icon={
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            }
            onClick={() => {
              window.history.pushState({}, '', '/inbox');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          />

          <DashboardCard
            title="PO Quotes"
            description="Upload a Purchase Order and automatically predict best-price quotes via AI."
            buttonText="Process PO"
            icon={
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            }
            onClick={() => {
              window.history.pushState({}, '', '/po-quote');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          />

          <DashboardCard
            title="Follow Ups"
            description="View the full sent pipeline — track every application from cold email through follow-up approval."
            buttonText="View Pipeline"
            icon={
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
              </svg>
            }
            onClick={() => {
              window.history.pushState({}, '', '/follow-ups');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          />

          <DashboardCard
            title="Sent Emails"
            description="Control your daily outgoing email limits to maintain high deliverability."
            buttonText="Emails Sent"
            icon={
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            onClick={() => {
              window.history.pushState({}, '', '/sending-review');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          />

          <DashboardCard
            title="New Reviews"
            description="For viewing and approving all the emails under review."
            buttonText="To be Reviewed"
            icon={
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            }
            onClick={() => {
              window.history.pushState({}, '', '/review');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          />

          <DashboardCard
            title="Market Data"
            description="Access real-time textile market data, competitor analysis, and AI-driven industry insights."
            buttonText="Analyze Markets"
            icon={
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            onClick={() => {
              window.history.pushState({}, '', '/market-intelligence');
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          />

        </div>
    </div>
  );
};

// Sub-component for clean, unified dashboard cards
const DashboardCard = ({ title, description, buttonText, icon, onClick }: any) => {
  return (
    <div className="relative group flex flex-col p-8 h-full bg-zinc-900/40 backdrop-blur-md rounded-2xl border border-white/5 hover:border-indigo-500/30 transition-all duration-500 shadow-xl hover:shadow-indigo-500/10 hover:-translate-y-1 overflow-hidden">
      {/* Subtle background glow effect on hover */}
      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      
      <div className="flex items-start justify-between mb-6 relative z-10">
        <div className="p-3 bg-white/5 text-zinc-300 rounded-xl border border-white/10 group-hover:text-indigo-400 group-hover:border-indigo-500/30 transition-colors duration-500">
          {icon}
        </div>
      </div>

      <h2 className="text-xl font-bold mb-2 text-white tracking-tight relative z-10">{title}</h2>
      <p className="text-zinc-400 text-sm mb-8 flex-grow leading-relaxed relative z-10">{description}</p>

      <button
        onClick={onClick}
        className="w-full mt-auto relative z-10 bg-white/5 text-zinc-300 font-semibold py-3 text-sm rounded-xl border border-white/10 hover:bg-indigo-500 hover:text-white hover:border-indigo-400 transition-all duration-300 shadow-md"
      >
        {buttonText}
      </button>
    </div>
  );
};

export default DashboardPage;