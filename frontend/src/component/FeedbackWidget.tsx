import React, { useState } from 'react';

interface FeedbackWidgetProps {
  section: string;
  userInput: string;
  agentResponse: string;
}

const FeedbackWidget: React.FC<FeedbackWidgetProps> = ({ section, userInput, agentResponse }) => {
  const [submitted, setSubmitted] = useState(false);

  const sendFeedback = async (type: 'good' | 'bad') => {
    try {
      await fetch('http://localhost:5050/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section,
          user_input: userInput,
          agent_response: agentResponse,
          feedback: type,
        }),
      });
      setSubmitted(true);
    } catch (error) {
      console.error('Feedback failed', error);
    }
  };

  if (submitted) return <p className="text-xs text-emerald-500 font-bold mt-2">Thanks for your feedback!</p>;

  return (
    <div className="flex items-center gap-2 mt-4 p-2 bg-white/5 rounded-lg border border-white/10 w-fit">
      <span className="text-[10px] uppercase font-bold text-zinc-500 mr-2">Feedback:</span>
      <button
        onClick={() => sendFeedback('good')}
        className="px-3 py-1 bg-emerald-500/10 hover:bg-emerald-500 text-emerald-500 hover:text-white text-[10px] font-bold rounded transition-all border border-emerald-500/20"
      >
        👍 Good
      </button>
      <button
        onClick={() => sendFeedback('bad')}
        className="px-3 py-1 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white text-[10px] font-bold rounded transition-all border border-red-500/20"
      >
        👎 Bad
      </button>
    </div>
  );
};

export default FeedbackWidget;
