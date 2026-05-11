import React, { useState, useEffect, useRef } from 'react';
import EmailDraftFeedbackWidget from '../component/EmailDraftFeedbackWidget';



interface EmailEditorProps {
    id: string;
    onLogout?: () => void;
}

export default function EmailEditor({ id, onLogout }: EmailEditorProps) {
    // Determine if this is a cold email or follow-up from URL params
    const emailType = (new URLSearchParams(window.location.search).get('type') || 'cold') as 'cold' | 'followup';
    const editorRef = useRef<HTMLDivElement>(null);
    const [role, setRole] = useState<string>('');
    const [company, setCompany] = useState<string>('');
    const [subject, setSubject] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [aiLoading, setAiLoading] = useState(false);
    const [lastUserMessage, setLastUserMessage] = useState('');
    const [aiDraft, setAiDraft] = useState('');
    const [feedback, setFeedback] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [autoSaved, setAutoSaved] = useState(false);
    
    // Strategic Context State (New: based on MLOps report)
    const [senderRole, setSenderRole] = useState<'Marketing Manager' | 'Executive' | 'Expert'>('Marketing Manager');
    const [strategicFocus, setStrategicFocus] = useState<string[]>(['Concise', 'Authority']);
    const lastSavedContent = useRef<string>('');
    const lastSavedSubject = useRef<string>('');

    // Link Modal State
    const [showLinkModal, setShowLinkModal] = useState(false);
    const [linkUrl, setLinkUrl] = useState('');
    const [linkText, setLinkText] = useState('');
    const [savedRange, setSavedRange] = useState<Range | null>(null);

    // Image Input Ref
    const fileInputRef = useRef<HTMLInputElement>(null);

    const formatForEditor = (text: string) => {
        if (!text) return '';
        
        // Handle basic Markdown-style bolding **text** -> <b>text</b>
        let formatted = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
        
        // Handle basic Markdown-style bullet points - text -> • text
        formatted = formatted.replace(/^- (.*)$/gm, '• $1');

        if (formatted.includes('<p>') || formatted.includes('<br')) return formatted;
        return formatted.replace(/\n/g, '<br />');
    };

    const applyStyle = (command: string, value: string | undefined = undefined) => {
        document.execCommand(command, false, value);
        editorRef.current?.focus();
    };


    useEffect(() => {
        // Route to the correct DB endpoint based on type
        const endpoint = emailType === 'followup'
            ? `/api/review/followup/${id}`
            : `/api/tracking/${id}`;

        fetch(endpoint)
            .then(res => {
                if (!res.ok) throw new Error('Failed to fetch record');
                return res.json();
            })
            .then(data => {
                setRole(data.role);
                setCompany(data.company_email);
                const payload = typeof data.body_json === 'string' ? JSON.parse(data.body_json) : data.body_json;
                const initialContent = payload.body?.generated_content || '';
                const initialSubject = payload.body?.subject || data.generated_subject || '';
                setSubject(initialSubject);
                setAiDraft(initialContent); // Populate aiDraft on load
                if (editorRef.current) editorRef.current.innerHTML = formatForEditor(initialContent);
                lastSavedContent.current = formatForEditor(initialContent);
                lastSavedSubject.current = initialSubject;
                setLoading(false);
            })
            .catch(err => {
                setError(err.message);
                setLoading(false);
            });
    }, [id]);

    const performSave = async (isSilent = false, overrideContent?: string): Promise<boolean> => {
        const content = overrideContent !== undefined ? overrideContent : (editorRef.current?.innerHTML || '');
        
        // Prevent 400 Bad Request if content is somehow empty
        if (!content) return false;

        if (isSilent && content === lastSavedContent.current && subject === lastSavedSubject.current) return true;

        if (!isSilent) setSaving(true);
        const saveUrl = emailType === 'followup'
            ? `/api/review/followup/${id}/save`
            : `/api/tracking/${id}/save`;
        try {
            const res = await fetch(saveUrl, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_content: content, subject })
            });
            if (!res.ok) throw new Error('Save failed');
            
            lastSavedContent.current = content;
            lastSavedSubject.current = subject;
            
            if (isSilent) {
                setAutoSaved(true);
                setTimeout(() => setAutoSaved(false), 3000);
            } else if (!overrideContent) {
                // Only alert on manual save, not silent or chained saves
                alert('Saved successfully!');
            }
            return true;
        } catch (err: any) {
            if (!isSilent) alert(`Error: ${err.message}`);
            return false;
        } finally {
            if (!isSilent) setSaving(false);
        }
    };

    const handleSave = () => performSave(false);

    const handleBack = async () => {
        // Trigger a final save before leaving
        await performSave(true);
        window.history.back();
    };

    // Auto-save effect: every 10 seconds check for changes
    useEffect(() => {
        const timer = setInterval(() => {
            if (!loading && !aiLoading && !saving) {
                performSave(true);
            }
        }, 10000);
        return () => clearInterval(timer);
    }, [id, loading, aiLoading, saving, subject, emailType]);

    const handleApprove = async () => {
        const saved = await performSave(true);
        if (!saved) return alert('Cannot approve: failed to save current draft.');
        setSaving(true);
        // Route approve to correct endpoint based on type
        const approveUrl = emailType === 'followup'
            ? `/api/review/followup/${id}/approve`
            : `/api/tracking/${id}/status`;
        try {
            const body = emailType === 'followup' ? '{}' : JSON.stringify({ status: 'Approved' });
            const res = await fetch(approveUrl, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body,
            });
            if (!res.ok) throw new Error('Status update failed');
            alert('Email Approved successfully!');
            window.history.back();
        } catch (err: any) {
            alert(`Error: ${err.message}`);
        } finally {
            setSaving(false);
        }
    };

    const handleLinkClick = () => {
        const sel = window.getSelection();
        if (sel && sel.rangeCount > 0) {
            setSavedRange(sel.getRangeAt(0));
            setLinkText(sel.toString());
        } else {
            setSavedRange(null);
            setLinkText('');
        }
        setLinkUrl('');
        setShowLinkModal(true);
    };

    const submitLink = () => {
        if (savedRange) {
            const sel = window.getSelection();
            sel?.removeAllRanges();
            sel?.addRange(savedRange);
        } else {
            editorRef.current?.focus();
        }

        const html = `<a href="${linkUrl}" class="text-blue-400 hover:text-blue-300 underline" target="_blank">${linkText || linkUrl}</a>`;
        document.execCommand('insertHTML', false, html);
        setShowLinkModal(false);
    };

    const handleImageSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (evt) => {
                const dataUrl = evt.target?.result as string;
                editorRef.current?.focus();
                document.execCommand('insertHTML', false, `<br/><img src="${dataUrl}" class="max-w-md rounded-lg my-2 shadow-lg border border-zinc-700/50" alt="inserted image" /><br/>`);
            };
            reader.readAsDataURL(file);
            // Reset input
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleAiRewrite = async () => {
        if (!feedback.trim()) return alert('Please enter feedback.');
        setAiLoading(true);
        setLastUserMessage(feedback);
        try {
            // Inject Strategic Context into the feedback to guide the AI better
            const enrichedFeedback = `[ROLE: ${senderRole}] [FOCUS: ${strategicFocus.join(', ')}] ${feedback}`;
            
            const res = await fetch(`/api/tracking/${id}/ai-edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback: enrichedFeedback })
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'AI rewrite failed');
            
            if (editorRef.current) {
                const newHtml = formatForEditor(data.new_content || '');
                editorRef.current.innerHTML = newHtml;
                setAiDraft(data.new_content);
                if (data.new_subject) setSubject(data.new_subject);
                
                // Trigger an immediate silent save after AI generation with the fresh content
                performSave(true, newHtml);
            }
            setFeedback('');
        } catch (err: any) {
            alert(`Error: ${err.message}`);
        } finally {
            setAiLoading(false);
        }
    };

    if (error) return <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-red-500 font-mono">ERROR: {error}</div>;
    if (loading) return <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-white font-mono">LOADING...</div>;

    return (
        <div className="min-h-screen w-full bg-zinc-950 text-zinc-100 font-sans flex flex-col relative overflow-hidden">
            {/* Background Layer */}
            <div className="fixed inset-0 z-0 bg-black" />
            <div className="fixed inset-0 z-0 bg-[radial-gradient(circle_at_50%_-20%,_#1e1e2e,_transparent)] pointer-events-none" />

            {/* Nav */}
            <nav className="relative z-20 w-full px-6 py-4 border-b border-zinc-800/50 bg-zinc-950/50 backdrop-blur-xl flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <button onClick={handleBack} className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-600 transition-colors">
                        <svg className="w-5 h-5 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
                    </button>
                    <span className="font-black tracking-tighter text-xl">EDITOR<span className="text-blue-500">.</span></span>
                </div>
                <button onClick={onLogout} className="px-4 py-2 text-xs font-bold text-zinc-500 hover:text-red-400 transition-colors">LOGOUT</button>
            </nav>

            {/* Main Content Area */}
            <main className="relative z-10 flex-grow flex flex-col items-center p-6 overflow-hidden">
                <div className="w-full max-w-7xl h-full flex flex-col gap-6">

                    {/* Top Info Bar */}
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-zinc-900/50 border border-zinc-800/50 rounded-2xl">
                        <div>
                            <div className="flex items-center gap-3">
                                <h2 className="text-xl font-bold text-white uppercase tracking-tight">{company || 'New Email'}</h2>
                                {autoSaved && (
                                    <span className="text-[10px] font-bold text-emerald-500 animate-pulse bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                                        AUTO-SAVED
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-3 mt-1">
                                <p className="text-sm text-zinc-500 font-medium">{role}</p>
                                <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-0.5 rounded-md border
                                    ${emailType === 'followup'
                                        ? 'bg-purple-500/15 text-purple-300 border-purple-500/30'
                                        : 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'}`}>
                                    {emailType === 'followup' ? 'FOLLOW-UP' : 'COLD EMAIL'}
                                </span>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <button
                                onClick={handleApprove}
                                className="px-8 py-3 bg-emerald-600/10 border border-emerald-500/50 hover:bg-emerald-600 hover:text-white text-emerald-400 text-sm font-bold rounded-xl transition-all shadow-lg shadow-emerald-900/20"
                            >
                                ✓ APPROVE
                            </button>
                            <button
                                onClick={handleSave}
                                disabled={saving || aiLoading}
                                className="px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-blue-900/20"
                            >
                                {saving ? 'SAVING...' : 'SAVE CHANGES'}
                            </button>
                        </div>
                    </div>

                    {/* Editor Grid */}
                    <div className="flex-grow grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">

                        {/* Left Column: Editor (8/12) */}
                        <div className="lg:col-span-8 flex flex-col bg-zinc-900/30 border border-zinc-800/50 rounded-2xl overflow-hidden shadow-2xl">

                            {/* Strategic Context Controls (New) */}
                            <div className="flex flex-wrap items-center gap-4 p-4 bg-zinc-900/50 border-b border-zinc-800/50">
                                <div className="flex items-center gap-2 mr-2">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Sender Role:</span>
                                    <div className="flex bg-black/40 rounded-lg p-1 border border-zinc-800">
                                        {['Marketing Manager', 'Executive', 'Expert'].map((r) => (
                                            <button
                                                key={r}
                                                onClick={() => setSenderRole(r as any)}
                                                className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all ${senderRole === r ? 'bg-blue-600 text-white shadow-lg' : 'text-zinc-500 hover:text-zinc-300'}`}
                                            >
                                                {r}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">AI Focus:</span>
                                    <div className="flex gap-2">
                                        {['Concise', 'Authority', 'Value-First', 'Warm'].map((tag) => (
                                            <button
                                                key={tag}
                                                onClick={() => setStrategicFocus(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])}
                                                className={`px-2.5 py-1 text-[10px] font-bold rounded-full border transition-all ${strategicFocus.includes(tag) ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400' : 'border-zinc-800 text-zinc-500 hover:border-zinc-700'}`}
                                            >
                                                {tag}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Subject Editor */}
                            <div className="flex items-center gap-3 p-4 bg-zinc-900/80 border-b border-zinc-800/50">
                                <span className="text-xs font-bold uppercase tracking-widest text-zinc-500">Subject:</span>
                                <input
                                    type="text"
                                    value={subject}
                                    onChange={(e) => setSubject(e.target.value)}
                                    className="flex-grow bg-black/20 border border-zinc-700 rounded-lg px-3 py-1.5 text-zinc-200 text-sm focus:outline-none focus:border-blue-500/50 transition-colors placeholder:text-zinc-600 font-semibold"
                                    placeholder="Enter email subject line..."
                                />
                            </div>

                            {/* ToolBar */}
                            <div className="flex items-center gap-1 p-2 bg-zinc-900/80 border-b border-zinc-800/50">
                                <ToolbarButton onClick={() => applyStyle('bold')} label="B" bold />
                                <ToolbarButton onClick={() => applyStyle('italic')} label="I" italic />
                                <ToolbarButton onClick={() => applyStyle('underline')} label="U" underline />
                                <div className="w-px h-4 bg-zinc-800 mx-2" />
                                <ToolbarButton onClick={() => applyStyle('insertUnorderedList')} label="List" />
                                <div className="w-px h-4 bg-zinc-800 mx-2" />
                                <ToolbarButton onClick={handleLinkClick} label="🔗 Link" />
                                <ToolbarButton onClick={() => fileInputRef.current?.click()} label="Image" />
                                <input
                                    type="file"
                                    accept="image/*"
                                    ref={fileInputRef}
                                    onChange={handleImageSelected}
                                    className="hidden"
                                />
                            </div>

                            {/* Editing Area */}
                            <div
                                ref={editorRef}
                                contentEditable
                                spellCheck={true}
                                className="editor-content flex-grow p-8 text-zinc-300 font-sans text-lg leading-relaxed focus:outline-none overflow-y-auto no-scrollbar"
                            />
                        </div>

                        {/* Right Column: AI (4/12) */}
                        <div className="lg:col-span-4 flex flex-col gap-4 min-h-0">
                            <div className="flex-grow flex flex-col p-6 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl backdrop-blur-sm overflow-hidden">
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                    <h3 className="text-xs font-bold uppercase tracking-widest text-emerald-500">AI Refinement</h3>
                                </div>

                                <textarea
                                    value={feedback}
                                    onChange={(e) => setFeedback(e.target.value)}
                                    placeholder="Ask the AI to change the tone, length, or focus..."
                                    className="flex-grow w-full p-4 bg-black/20 border border-zinc-800/50 rounded-xl text-zinc-200 text-sm focus:outline-none focus:border-emerald-500/30 transition-colors resize-none placeholder:text-zinc-700 no-scrollbar"
                                />

                                <button
                                    onClick={handleAiRewrite}
                                    disabled={aiLoading || saving}
                                    className="mt-4 w-full py-4 bg-emerald-600/10 hover:bg-emerald-600 border border-emerald-500/20 text-emerald-500 hover:text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2"
                                >
                                    {aiLoading ? 'PROCESSING...' : 'REWRITE WITH AI'}
                                </button>
                                {!aiLoading && (
                                    <EmailDraftFeedbackWidget 
                                        userInput={lastUserMessage || 'Initial Generation'}
                                        agentResponse={aiDraft || (editorRef.current?.innerText || '')}
                                    />
                                )}
                            </div>

                            {/* Tips Box */}
                            <div className="p-4 bg-blue-500/5 border border-blue-500/10 rounded-2xl">
                                <p className="text-[10px] leading-relaxed text-zinc-500 uppercase font-bold tracking-widest mb-1">Editor Tip</p>
                                <p className="text-xs text-zinc-400">Typos have red underlines automatically. Inserted images will resize to fit.</p>
                            </div>
                        </div>

                    </div>
                </div>
            </main>

            <style>{`
                /* Scrollbar Hiding */
                .no-scrollbar::-webkit-scrollbar {
                    display: none;
                }
                .no-scrollbar {
                    -ms-overflow-style: none;
                    scrollbar-width: none;
                }
                
                /* Tilted Links Styling */
                .editor-content a {
                    display: inline-block;
                    transform: rotate(-2deg);
                    color: #60a5fa; /* Tailwind Blue-400 */
                    text-decoration: underline;
                    transition: transform 0.2s ease, color 0.2s ease;
                }
                
                /* Straighten link on hover */
                .editor-content a:hover {
                    transform: rotate(0deg);
                    color: #93c5fd; /* Tailwind Blue-300 */
                }

                /* Ensure inserted images don't break the layout */
                .editor-content img {
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    margin: 12px 0;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
                
                main { height: calc(100vh - 73px); } 
            `}</style>

            {/* Custom Link Modal Overlay */}
            {showLinkModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <div className="w-full max-w-sm bg-zinc-900 border border-zinc-700/80 rounded-2xl shadow-2xl p-6 flex flex-col gap-4">
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="text-lg font-bold text-white">Insert Link</h3>
                            <button onClick={() => setShowLinkModal(false)} className="text-zinc-500 hover:text-white transition">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                        </div>

                        <div className="flex flex-col gap-1">
                            <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Text to display</label>
                            <input
                                type="text"
                                value={linkText}
                                onChange={e => setLinkText(e.target.value)}
                                placeholder="e.g. Click here"
                                className="w-full p-3 bg-black/40 border border-zinc-700 rounded-xl text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                            />
                        </div>

                        <div className="flex flex-col gap-1">
                            <label className="text-xs font-bold text-zinc-400 uppercase tracking-wider">URL</label>
                            <input
                                type="url"
                                value={linkUrl}
                                onChange={e => setLinkUrl(e.target.value)}
                                placeholder="https://example.com"
                                className="w-full p-3 bg-black/40 border border-zinc-700 rounded-xl text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                            />
                        </div>

                        <button
                            onClick={submitLink}
                            disabled={!linkUrl.trim()}
                            className="mt-2 w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-bold rounded-xl transition-all"
                        >
                            INSERT LINK
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

function ToolbarButton({ onClick, label, bold, italic, underline }: any) {
    return (
        <button
            onClick={(e) => { e.preventDefault(); onClick(); }}
            className={`min-w-[32px] h-8 px-2 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white transition-all text-xs font-bold
        ${bold ? 'font-serif' : ''} ${italic ? 'italic' : ''} ${underline ? 'underline' : ''}`}
        >
            {label}
        </button>
    );
}