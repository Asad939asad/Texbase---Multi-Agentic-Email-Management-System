import React, { useState } from 'react';

interface Props {
  userInput: string;
  agentResponse: string;
}

const EmailDraftFeedbackWidget: React.FC<Props> = ({ userInput, agentResponse }) => {
  const [submitted, setSubmitted] = useState(false);
  const [hovered, setHovered] = useState<'up' | 'down' | null>(null);

  const sendFeedback = async (type: 'good' | 'bad') => {
    try {
      await fetch('http://localhost:5050/api/feedback/email_editor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: type,
          user_input: userInput || 'Initial Draft (No specific feedback given)',
          agent_response: agentResponse || '',
          draft_length_chars: (agentResponse || '').length
        }),
      });
      setSubmitted(true);
    } catch (e) { console.error(e); }
  };

  if (submitted) return (
    <div style={{ marginTop: '15px', padding: '10px', background: '#10b98110', border: '1px solid #10b98130', borderRadius: '8px', textAlign: 'center' }}>
      <p style={{ color: '#10b981', fontSize: '12px', fontWeight: 'bold', margin: 0 }}>
        Thanks for the feedback! 🚀
      </p>
    </div>
  );

  return (
    <div style={{ marginTop: '20px', padding: '15px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8', fontWeight: 600 }}>Was this draft helpful?</p>
      <div style={{ display: 'flex', gap: '12px' }}>
        <button 
          onMouseEnter={() => setHovered('up')}
          onMouseLeave={() => setHovered(null)}
          onClick={() => sendFeedback('good')} 
          style={{ 
            padding: '8px', 
            background: hovered === 'up' ? '#10b98120' : 'transparent', 
            color: hovered === 'up' ? '#10b981' : '#94a3b8', 
            border: 'none', 
            borderRadius: '50%', 
            cursor: 'pointer', 
            fontSize: '20px',
            transition: 'all 0.2s ease'
          }}
          title="Helpful"
        >
          👍
        </button>
        <button 
          onMouseEnter={() => setHovered('down')}
          onMouseLeave={() => setHovered(null)}
          onClick={() => sendFeedback('bad')} 
          style={{ 
            padding: '8px', 
            background: hovered === 'down' ? '#ef444420' : 'transparent', 
            color: hovered === 'down' ? '#ef4444' : '#94a3b8', 
            border: 'none', 
            borderRadius: '50%', 
            cursor: 'pointer', 
            fontSize: '20px',
            transition: 'all 0.2s ease'
          }}
          title="Not helpful"
        >
          👎
        </button>
      </div>
    </div>
  );
};

export default EmailDraftFeedbackWidget;
