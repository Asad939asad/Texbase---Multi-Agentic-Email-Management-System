import React, { useState } from 'react';

interface Props {
  actionDescription: string;
  outcomeMessage: string;
  pipelineStage: string;
}

const PipelineFeedbackWidget: React.FC<Props> = ({ actionDescription, outcomeMessage, pipelineStage }) => {
  const [submitted, setSubmitted] = useState(false);

  const send = async (type: 'good' | 'partial' | 'bad') => {
    try {
      await fetch('http://localhost:5050/api/feedback/inbox_flow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: type,
          user_input: actionDescription,
          agent_response: outcomeMessage,
          pipeline_stage: pipelineStage,
          recipient_hint: "Anonymized"
        }),
      });
      setSubmitted(true);
    } catch (e) { console.error(e); }
  };

  if (submitted) return <p style={{color: '#94a3b8', fontSize: '11px', fontWeight: 'bold', marginTop: '8px'}}>Logged. Failed actions are reviewed in the next analysis run.</p>;

  return (
    <div style={{marginTop: '15px', padding: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)'}}>
      <p style={{margin: '0 0 10px 0', fontSize: '12px', color: '#64748b', fontWeight: 600}}>Did this email action complete correctly?</p>
      <div style={{display: 'flex', gap: '8px'}}>
        <button onClick={() => send('good')} style={{padding: '5px 10px', background: '#10b98110', color: '#4ade80', border: '1px solid #10b98120', borderRadius: '5px', cursor: 'pointer', fontSize: '10px', fontWeight: 'bold'}}>Yes, completed</button>
        <button onClick={() => send('partial')} style={{padding: '5px 10px', background: '#f59e0b10', color: '#fbbf24', border: '1px solid #f59e0b20', borderRadius: '5px', cursor: 'pointer', fontSize: '10px', fontWeight: 'bold'}}>Partial issue</button>
        <button onClick={() => send('bad')} style={{padding: '5px 10px', background: '#ef444410', color: '#f87171', border: '1px solid #ef444420', borderRadius: '5px', cursor: 'pointer', fontSize: '10px', fontWeight: 'bold'}}>Failed</button>
      </div>
    </div>
  );
};

export default PipelineFeedbackWidget;
