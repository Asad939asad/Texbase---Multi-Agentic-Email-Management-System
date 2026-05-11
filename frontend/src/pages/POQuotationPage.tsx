import React, { useState, useEffect } from 'react';
import ElectricBorder from '../component/ElectricBorder';
import QuotationFeedbackWidget from '../component/QuotationFeedbackWidget';



interface PredictionRow {
  row_index?: number;
  item?: string;
  description?: string;
  quantity?: string | number;
  unit_price?: string | number;
  predicted_price_usd?: string | number;
  margin_applied_pct?: string | number;
  prediction_reasoning?: string;
}

export default function POQuotationPage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [predictions, setPredictions] = useState<PredictionRow[]>([]);

  // New States for Database Browsing
  const [existingTables, setExistingTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableRows, setTableRows] = useState<any[]>([]);
  const [tableLoading, setTableLoading] = useState(false);
  const [isPredicting, setIsPredicting] = useState(false);
  const [pipelineLog, setPipelineLog] = useState<string[]>([]);

  // Fetch tables on mount
  useEffect(() => {
    fetchTables();
  }, []);

  // Polling for logs when loading
  useEffect(() => {
    let interval: any;
    if (loading) {
      interval = setInterval(async () => {
        try {
          const res = await fetch('/api/po/pipeline-status');
          const data = await res.json();
          if (data.log) setPipelineLog(data.log);
          if (data.status === 'done' || data.status === 'error') {
             // Stop polling if already finished
             // (though the main handleUpload finally block will set loading false)
          }
        } catch (err) { console.error('Log fetch error:', err); }
      }, 1000);
    } else {
      setPipelineLog([]); // Reset when not loading
    }
    return () => clearInterval(interval);
  }, [loading]);

  const fetchTables = async () => {
    try {
      const res = await fetch('/api/po/tables');
      const data = await res.json();
      if (data.tables) setExistingTables(data.tables);
    } catch (err) {
      console.error('Failed to fetch tables:', err);
    }
  };

  const handleTableSelect = async (tableName: string) => {
    setSelectedTable(tableName);
    setTableLoading(true);
    setPredictions([]); // Clear previous predictions
    try {
      // 1. Fetch Raw Table Data
      const resRaw = await fetch(`/api/po/table/${tableName}`);
      const dataRaw = await resRaw.json();
      if (dataRaw.success) {
        setTableRows(dataRaw.rows);
      }

      // 2. Fetch Existing Predictions if any
      const resPred = await fetch(`/api/po/predictions/${tableName}`);
      const dataPred = await resPred.json();
      if (dataPred.success && dataPred.predictions) {
        setPredictions(dataPred.predictions);
      }
    } catch (err) {
      console.error('Failed to fetch table data:', err);
    } finally {
      setTableLoading(false);
    }
  };

  const handlePredictTable = async () => {
    if (!selectedTable) return;
    setIsPredicting(true);
    setError(null);
    try {
      const res = await fetch('/api/po/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ table_name: selectedTable }),
      });
      const data = await res.json();
      if (data.success) {
        setPredictions(data.predictions);
      } else {
        setError(data.error || 'Prediction failed');
      }
    } catch (err: any) {
      setError(err.message || 'Network error');
    } finally {
      setIsPredicting(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setPredictions([]);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/po/process', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      
      if (data.success) {
        setPredictions(data.predictions || []);
        fetchTables(); // Refresh list
        
        // Automatically select the new table if one was created
        if (data.po_tables && data.po_tables.length > 0) {
          handleTableSelect(data.po_tables[0].table_name);
        }
      } else {
        setError(data.error || 'Failed to process PO');
      }
    } catch (err: any) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: '100vh', width: '100vw', background: '#050816', color: '#e2e8f0', fontFamily: "'Inter', sans-serif", display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ background: 'linear-gradient(135deg, #0f1729 0%, #1a1040 100%)', borderBottom: '1px solid rgba(99,102,241,.3)', padding: '16px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, zIndex: 30 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, background: 'linear-gradient(90deg, #818cf8, #c084fc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            PO to Quotation Automation
          </h1>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 2 }}>
            Manage and analyze Purchase Orders with AI-driven market intelligence.
          </div>
        </div>
        <button
          onClick={() => {
            window.history.pushState({}, '', '/dashboard');
            window.dispatchEvent(new PopStateEvent('popstate'));
          }}
          style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '6px 14px', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
        >
          ← Dashboard
        </button>
      </div>

      <div style={{ display: 'flex', flexGrow: 1, overflow: 'hidden' }}>
        {/* Sidebar: Database Tables */}
        <div style={{ width: 280, flexShrink: 0, background: 'rgba(15,23,42,0.4)', borderRight: '1px solid rgba(255,255,255,0.05)', padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ fontSize: '0.75rem', color: '#818cf8', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 16, fontWeight: 700 }}>History</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {existingTables.length === 0 && <div style={{ fontSize: '0.8rem', color: '#64748b', textAlign: 'center', padding: 20 }}>No records.</div>}
            {existingTables.map(t => (
              <button
                key={t}
                onClick={() => handleTableSelect(t)}
                style={{
                  textAlign: 'left',
                  padding: '10px 12px',
                  borderRadius: 8,
                  fontSize: '0.8rem',
                  border: '1px solid',
                  borderColor: selectedTable === t ? 'rgba(129,140,248,0.4)' : 'transparent',
                  background: selectedTable === t ? 'rgba(99,102,241,0.1)' : 'transparent',
                  color: selectedTable === t ? '#fff' : '#94a3b8',
                  cursor: 'pointer',
                  transition: 'all 0.1s',
                  wordBreak: 'break-all',
                  textTransform: 'capitalize'
                }}
              >
                {t.replace(/_po_line_items/g, '').replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Main Content Area */}
        <div style={{ flexGrow: 1, overflowY: 'auto', padding: '32px 40px', display: 'flex', flexDirection: 'column', gap: 32 }}>
          
          {/* Top: Upload Section */}
          <div style={{ background: 'rgba(15,23,42,.4)', padding: 20, borderRadius: 16, border: '1px dashed rgba(99,102,241,0.2)', textAlign: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
              <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Process New PO:</span>
              <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={handleFileChange} id="po-upload" style={{ display: 'none' }} />
              <label htmlFor="po-upload" style={{ display: 'inline-block', background: 'rgba(255,255,255,0.03)', color: '#cbd5e1', padding: '8px 16px', borderRadius: 8, cursor: 'pointer', border: '1px solid rgba(255,255,255,0.1)', fontSize: '0.8rem' }}>
                {file ? file.name : 'Choose File'}
              </label>
              
              <button 
                onClick={handleUpload}
                disabled={!file || loading}
                style={{
                  background: !file || loading ? '#334155' : 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                  color: '#fff',
                  padding: '8px 20px',
                  borderRadius: 8,
                  border: 'none',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: !file || loading ? 'not-allowed' : 'pointer'
                }}
              >
                {loading ? 'Processing...' : 'Upload & Analyze'}
              </button>
            </div>
            {error && <div style={{ color: '#f87171', marginTop: 10, fontSize: '0.75rem' }}>{error}</div>}

            {/* LIVE PIPELINE LOGS */}
            {loading && pipelineLog.length > 0 && (
              <div style={{ marginTop: 20, background: '#020617', borderRadius: 12, border: '1px solid rgba(99,102,241,0.3)', padding: '16px', textAlign: 'left', maxHeight: '250px', overflowY: 'auto', display: 'flex', flexDirection: 'column-reverse', boxShadow: 'inset 0 2px 10px rgba(0,0,0,0.5)' }}>
                <div style={{ fontSize: '0.75rem', fontFamily: "'Fira Code', monospace", color: '#94a3b8', lineHeight: '1.5' }}>
                  {pipelineLog.map((line, idx) => (
                    <div key={idx} style={{ marginBottom: 6, display: 'flex', gap: 10 }}>
                      <span style={{ color: '#6366f1', opacity: 0.7 }}>[{new Date().toLocaleTimeString([], { hour12: false })}]</span>
                      <span style={{ color: line.includes('[stderr]') ? '#f87171' : '#e2e8f0' }}>{line}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Middle: Selected Table Content */}
          {selectedTable && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0, textTransform: 'capitalize' }}>
                  PO Source: <span style={{ color: '#818cf8', fontSize: '0.95rem', fontWeight: 400 }}>{selectedTable.replace(/_po_line_items/g, '').replace(/_/g, ' ')}</span>
                </h2>
                <button
                  onClick={handlePredictTable}
                  disabled={isPredicting || tableLoading}
                  style={{
                    background: 'linear-gradient(90deg, #10b981, #059669)',
                    color: '#fff',
                    padding: '10px 24px',
                    borderRadius: 10,
                    border: 'none',
                    fontWeight: 700,
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    boxShadow: '0 4px 12px rgba(16,185,129,0.2)'
                  }}
                >
                  {isPredicting ? 'Analyzing Market...' : (predictions.length > 0 ? 'Re-Run Prediction' : 'Generate AI Quote')}
                </button>
              </div>

              {/* Raw Table */}
              <div style={{ background: 'rgba(15,23,42,0.5)', borderRadius: 12, border: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', tableLayout: 'auto' }}>
                    <thead>
                      <tr style={{ background: 'rgba(255,255,255,0.03)', color: '#94a3b8', textAlign: 'left' }}>
                        {tableRows.length > 0 && Object.keys(tableRows[0]).filter(k => k !== 'id').map(k => (
                          <th key={k} style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {tableRows.map((row, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                          {Object.entries(row).filter(([k]) => k !== 'id').map(([, v], j) => (
                            <td key={j} style={{ padding: '12px 16px', color: '#cbd5e1' }}>{String(v)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Prediction Table */}
              {(predictions.length > 0 || isPredicting) && (
                <>
                <ElectricBorder>
                  <div style={{ background: 'rgba(15,23,42,.85)', borderRadius: 16, padding: 24 }}>
                    <h3 style={{ margin: '0 0 20px', color: '#f8fafc', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 10px #10b981' }}></span>
                      AI Quotation Results
                    </h3>
                    
                    <div style={{ overflowX: 'auto', width: '100%' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', tableLayout: 'fixed' }}>
                        <thead>
                          <tr style={{ background: 'rgba(255,255,255,0.05)', textAlign: 'left', color: '#94a3b8' }}>
                            <th style={{ width: '20%', padding: '12px 10px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>Description</th>
                            <th style={{ width: '10%', padding: '12px 10px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>Qty</th>
                            <th style={{ width: '10%', padding: '12px 10px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>PO Price</th>
                            <th style={{ width: '12%', padding: '12px 10px', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#34d399' }}>AI Quote</th>
                            <th style={{ width: '8%', padding: '12px 10px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>Margin</th>
                            <th style={{ width: '40%', padding: '12px 10px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>Market Logic & Reasoning</th>
                          </tr>
                        </thead>
                        <tbody>
                          {predictions.map((p, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                              <td style={{ padding: '16px 10px', color: '#f8fafc', verticalAlign: 'top', wordBreak: 'break-word' }}>{p.description || p.item || 'N/A'}</td>
                              <td style={{ padding: '16px 10px', color: '#cbd5e1', verticalAlign: 'top' }}>{p.quantity || '-'}</td>
                              <td style={{ padding: '16px 10px', color: '#cbd5e1', verticalAlign: 'top' }}>{p.unit_price || '-'}</td>
                              <td style={{ padding: '16px 10px', color: '#10b981', fontWeight: 'bold', verticalAlign: 'top' }}>${p.predicted_price_usd}</td>
                              <td style={{ padding: '16px 10px', color: '#cbd5e1', verticalAlign: 'top' }}>{p.margin_applied_pct}%</td>
                              <td style={{ padding: '16px 10px', color: '#94a3b8', lineHeight: 1.6, fontSize: '0.75rem', verticalAlign: 'top', wordBreak: 'break-word' }}>
                                <ul style={{ margin: 0, paddingLeft: 16, listStyleType: 'disc' }}>
                                  {(p.prediction_reasoning || '').split(/(?:\. |\n)/).filter(s => s.trim().length > 10).map((sentence, idx) => (
                                    <li key={idx} style={{ marginBottom: 4 }}>{sentence.trim()}</li>
                                  ))}
                                </ul>
                              </td>
                            </tr>
                          ))}
                          {isPredicting && (
                            <tr>
                              <td colSpan={6} style={{ padding: 60, textAlign: 'center' }}>
                                <div style={{ color: '#818cf8', fontWeight: 600, animation: 'pulse 2s infinite' }}>
                                  Analyzing Market Trends & Risks...
                                </div>
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </ElectricBorder>
                {predictions.length > 0 && (
                  <QuotationFeedbackWidget 
                    userInput={`PO: ${selectedTable || 'Unknown'} | Items: ${predictions.length} | File: ${selectedTable || 'Manual'}`}
                    predictedPrice={parseFloat(predictions[0]?.predicted_price_usd?.toString() || '0')}
                    itemDescription={predictions[0]?.description || 'Multiple Items'}
                    responseText={JSON.stringify(predictions)} 
                  />
                )}
                </>
              )}

            </div>
          )}
          
          {!selectedTable && (
            <div style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: 0.3 }}>
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              <div style={{ marginTop: 16, fontSize: '0.9rem' }}>Select a Purchase Order from the history to begin</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
