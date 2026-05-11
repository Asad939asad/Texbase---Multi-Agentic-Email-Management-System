import React, { useState } from 'react';

interface Props {
  userInput: string;
  predictedPrice: number | null;
  itemDescription: string;
  responseText: string;
}

const QuotationFeedbackWidget: React.FC<Props> = ({ userInput, predictedPrice, itemDescription, responseText }) => {
  const [step, setStep] = useState<'initial' | 'correction' | 'submitted'>('initial');
  const [note, setNote] = useState('');

  const send = async (type: 'good' | 'bad', correctionNote?: string) => {
    try {
      await fetch('http://localhost:5050/api/feedback/po_quotation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: type,
          user_input: userInput,
          agent_response: responseText,
          predicted_price: predictedPrice,
          item_description: itemDescription,
          correction_note: correctionNote
        }),
      });
      setStep('submitted');
    } catch (e) { console.error(e); }
  };

  if (step === 'submitted') return (
    <div style={{ marginTop: '15px', padding: '10px', background: '#10b98110', border: '1px solid #10b98130', borderRadius: '8px' }}>
      <p style={{ color: '#10b981', fontSize: '12px', fontWeight: 'bold', margin: 0 }}>
        Feedback recorded. This correction will be used to retrain the price model.
      </p>
    </div>
  );

  return (
    <div style={{ marginTop: '20px', padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.08)' }}>
      <p style={{ margin: '0 0 15px 0', fontSize: '14px', color: '#e2e8f0', fontWeight: 600 }}>Was this price prediction accurate?</p>
      
      {step === 'initial' ? (
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            onClick={() => setStep('correction')} 
            style={{ padding: '10px 20px', background: '#10b98115', color: '#10b981', border: '1px solid #10b98130', borderRadius: '10px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold', transition: 'all 0.2s' }}
          >
            ✓ Accurate
          </button>
          <button 
            onClick={() => setStep('correction')} 
            style={{ padding: '10px 20px', background: '#ef444415', color: '#ef4444', border: '1px solid #ef444430', borderRadius: '10px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold', transition: 'all 0.2s' }}
          >
            ✕ Inaccurate
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <p style={{ margin: '10px 0 5px 0', fontSize: '13px', color: '#94a3b8' }}>
            Tell us about your experience. What did you like? What could be improved?
          </p>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="I liked the market sourcing details, but the unit conversion for '10kg' felt slightly off..."
            style={{ width: '100%', minHeight: '100px', padding: '12px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', color: '#fff', fontSize: '13px', outline: 'none' }}
          />
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={() => send(note.toLowerCase().includes('good') || note.length < 10 ? 'good' : 'bad', note)} 
              style={{ flex: 1, padding: '10px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold' }}
            >
              Submit Feedback
            </button>
            <button 
              onClick={() => setStep('initial')} 
              style={{ padding: '10px 15px', background: 'transparent', color: '#94a3b8', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', cursor: 'pointer', fontSize: '13px' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default QuotationFeedbackWidget;
