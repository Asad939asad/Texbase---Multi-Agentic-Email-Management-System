import React, { useState } from 'react';

interface Props {
  parameterName: string;
  predictionSummary: string;
  fullResponse: string;
}

const MarketFeedbackWidget: React.FC<Props> = ({ parameterName, predictionSummary, fullResponse }) => {
  const [step, setStep] = useState<'initial' | 'annotate' | 'submitted'>('initial');
  const [comment, setComment] = useState('');

  const send = async (type: 'good' | 'bad', annotation?: { excerpt: string; comment: string }) => {
    try {
      await fetch('http://localhost:5050/api/feedback/market_analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: type,
          user_input: `Market prediction for: ${parameterName}`,
          agent_response: fullResponse,
          parameter_name: parameterName,
          prediction_summary: predictionSummary,
          flagged_excerpt: annotation?.excerpt,
          user_comment: annotation?.comment
        }),
      });
      setStep('submitted');
    } catch (e) { console.error(e); }
  };

  if (step === 'submitted') return (
    <div style={{ marginTop: '15px', padding: '10px', background: '#10b98110', border: '1px solid #10b98130', borderRadius: '8px' }}>
      <p style={{ color: '#10b981', fontSize: '12px', fontWeight: 'bold', margin: 0 }}>
        Analysis feedback recorded. Our strategists will review this for model refinement.
      </p>
    </div>
  );

  return (
    <div style={{ marginTop: '20px', padding: '20px', background: 'rgba(255,255,255,0.03)', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.1)' }}>
      <p style={{ margin: '0 0 15px 0', fontSize: '14px', color: '#94a3b8', fontWeight: 600 }}>Was this market intelligence accurate?</p>
      
      {step === 'initial' ? (
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            onClick={() => setStep('annotate')} 
            style={{ padding: '10px 20px', background: '#10b98115', color: '#10b981', border: '1px solid #10b98130', borderRadius: '10px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold' }}
          >
            ✓ Accurate
          </button>
          <button 
            onClick={() => setStep('annotate')} 
            style={{ padding: '10px 20px', background: '#ef444415', color: '#ef4444', border: '1px solid #ef444430', borderRadius: '10px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold' }}
          >
            ✕ Inaccurate
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <p style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#94a3b8' }}>
              Tell us about your experience with this market analysis. What was helpful? What was missing?
            </p>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="I liked the depth of sourcing, but it missed the impact of current shipping delays in the Red Sea..."
              style={{ width: '100%', minHeight: '100px', padding: '10px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff', fontSize: '13px', outline: 'none' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={() => send(comment.toLowerCase().includes('good') || comment.length < 10 ? 'good' : 'bad', { excerpt: '', comment: comment })} 
              style={{ flex: 1, padding: '12px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: '10px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold' }}
            >
              Submit Feedback
            </button>
            <button 
              onClick={() => setStep('initial')} 
              style={{ padding: '12px 15px', background: 'transparent', color: '#94a3b8', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', cursor: 'pointer', fontSize: '13px' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MarketFeedbackWidget;
