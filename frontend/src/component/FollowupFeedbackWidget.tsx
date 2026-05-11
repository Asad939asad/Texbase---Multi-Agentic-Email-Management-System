import React, { useState } from 'react';

interface Props {
  summary: string;
  context: string;
  appId: string;
}

const FollowupFeedbackWidget: React.FC<Props> = ({ summary, context, appId }) => {
  const [submitted, setSubmitted] = useState(false);
  const [comment, setComment] = useState('');
  const [hovered, setHovered] = useState<'up' | 'down' | null>(null);

  const sendFeedback = async (type: 'good' | 'bad') => {
    try {
      await fetch('http://localhost:5050/api/feedback/inbox_flow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: type,
          user_input: `Pipeline Review for App ID: ${appId}${comment ? ' | Comment: ' + comment : ''}`,
          agent_response: summary,
          pipeline_stage: 'followup_review',
          recipient_hint: context.substring(0, 100)
        }),
      });
      setSubmitted(true);
    } catch (e) { console.error(e); }
  };

  if (submitted) return (
    <div style={{ marginTop: '10px', padding: '10px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '8px', textAlign: 'center' }}>
      <p style={{ color: '#10b981', fontSize: '11px', fontWeight: 'bold', margin: 0 }}>
        Feedback received! Pipeline optimized. 🎯
      </p>
    </div>
  );

  return (
    <div style={{ marginTop: '15px', padding: '15px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
      <p style={{ margin: '0 0 10px 0', fontSize: '12px', color: '#94a3b8', fontWeight: 600 }}>Was the follow-up analysis helpful?</p>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Any specific thoughts on the analysis or draft? (Optional)"
          style={{ 
            width: '100%', 
            minHeight: '60px', 
            padding: '10px', 
            background: 'rgba(0,0,0,0.2)', 
            border: '1px solid rgba(255,255,255,0.1)', 
            borderRadius: '8px', 
            color: '#fff', 
            fontSize: '12px', 
            outline: 'none',
            resize: 'none'
          }}
        />
        
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '15px' }}>
          <button 
            onMouseEnter={() => setHovered('up')}
            onMouseLeave={() => setHovered(null)}
            onClick={() => sendFeedback('good')} 
            style={{ 
              background: 'transparent', 
              color: hovered === 'up' ? '#10b981' : '#64748b', 
              border: 'none', 
              cursor: 'pointer', 
              fontSize: '22px',
              transition: 'all 0.2s ease',
              padding: '4px'
            }}
            title="Good Analysis"
          >
            👍
          </button>
          <button 
            onMouseEnter={() => setHovered('down')}
            onMouseLeave={() => setHovered(null)}
            onClick={() => sendFeedback('bad')} 
            style={{ 
              background: 'transparent', 
              color: hovered === 'down' ? '#ef4444' : '#64748b', 
              border: 'none', 
              cursor: 'pointer', 
              fontSize: '22px',
              transition: 'all 0.2s ease',
              padding: '4px'
            }}
            title="Poor Analysis"
          >
            👎
          </button>
        </div>
      </div>
    </div>
  );
};

export default FollowupFeedbackWidget;
