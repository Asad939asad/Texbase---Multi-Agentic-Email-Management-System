import { useEffect, useRef, useState } from 'react';
import Silk from '../component/Silk';

export default function LoginPage({ onLogout }: { onLogout?: () => void }) {
    const cursorRef = useRef<HTMLDivElement>(null);

    // Custom cursor tracking
    useEffect(() => {
        const move = (e: MouseEvent) => {
            if (cursorRef.current) {
                cursorRef.current.style.transform = `translate(${e.clientX - 6}px, ${e.clientY - 6}px)`;
            }
        };
        window.addEventListener('mousemove', move);
        return () => window.removeEventListener('mousemove', move);
    }, []);

    const [loading, setLoading] = useState(false);
    const [sessionData, setSessionData] = useState<{name: string, email: string} | null>(null);

    // Check if database.json has an active session
    useEffect(() => {
        fetch('http://localhost:8000/api/auth/session')
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data && data.email) {
                    setSessionData(data);
                }
            })
            .catch(err => console.error('Session check failed:', err));
    }, []);

    const handleGoogleLogin = async () => {
        console.log('Button clicked!');
        // setLoading(true);
        try {
            const response = await fetch('http://localhost:8000/api/auth/google');
            const data = await response.json();
            console.log('Got URL:', data.url);
            window.location.href = data.url;
        } catch (error) {
            console.error('Failed to reach the backend.', error);
            setLoading(false);
        }
    };

    return (
        /* Full-screen wrapper — fixed so it always covers the viewport */
        <div style={{
            position: 'fixed',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#255efaff',
            overflow: 'hidden',
            cursor: 'none',   /* hide default cursor */
        }}>

            {/* ── Custom cursor dot ── */}
            <div ref={cursorRef} style={{
                position: 'fixed',
                top: 0,
                left: 0,
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(165,180,252,0.9) 0%, rgba(99,102,241,0.4) 60%, transparent 100%)',
                pointerEvents: 'none',
                zIndex: 9999,
                transition: 'transform 0.04s linear',
                boxShadow: '0 0 8px rgba(113, 241, 99, 0.8), 0 0 16px rgba(99,102,241,0.4)',
            }} />


            {/* ── 1. FULL-SCREEN SILK BACKGROUND ── */}
            <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
                <Silk />
                {/* Brightened overlay for better visibility */}
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'radial-gradient(circle at center, transparent 0%, rgba(3,7,18,0.4) 100%)',
                    pointerEvents: 'none',
                }} />
            </div>

            {/* ── 2. GLASSMORPHISM LOGIN CARD ── */}
            <div style={{
                position: 'relative',
                zIndex: 10,
                width: '100%',
                maxWidth: '420px',
                margin: '0 16px',
                padding: '40px 36px',
                borderRadius: '24px',
                /* Glass effect */
                background: 'rgba(255, 255, 255, 0.04)',
                backdropFilter: 'blur(24px)',
                WebkitBackdropFilter: 'blur(24px)',
                border: '1px solid rgba(255,255,255,0.12)',
                /* Glow */
                boxShadow: `
                    0 0 0 1px rgba(99,102,241,0.15),
                    0 20px 60px rgba(0,0,0,0.6),
                    0 0 80px rgba(99,102,241,0.08),
                    inset 0 1px 0 rgba(255,255,255,0.08)
                `,
                transition: 'border-color 0.3s ease, box-shadow 0.3s ease',
            }}
                onMouseEnter={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.22)';
                    (e.currentTarget as HTMLDivElement).style.boxShadow = `
                        0 0 0 1px rgba(99,102,241,0.3),
                        0 20px 60px rgba(0,0,0,0.7),
                        0 0 100px rgba(99,102,241,0.15),
                        inset 0 1px 0 rgba(255,255,255,0.1)
                    `;
                }}
                onMouseLeave={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.12)';
                    (e.currentTarget as HTMLDivElement).style.boxShadow = `
                        0 0 0 1px rgba(99,102,241,0.15),
                        0 20px 60px rgba(0,0,0,0.6),
                        0 0 80px rgba(99,102,241,0.08),
                        inset 0 1px 0 rgba(255,255,255,0.08)
                    `;
                }}
            >
                {/* Icon */}
                <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                    <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '64px',
                        height: '64px',
                        borderRadius: '16px',
                        background: 'linear-gradient(135deg, #65f163ff, #a855f7)',
                        boxShadow: '0 8px 32px rgba(99,102,241,0.4)',
                        marginBottom: '24px',
                    }}>
                        <svg width="28" height="28" fill="none" stroke="white" strokeWidth="2"
                            strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
                            <path d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    </div>

                    <h1 style={{
                        margin: '0 0 8px',
                        fontSize: '28px',
                        fontWeight: 800,
                        color: '#f9fbfbff',
                        letterSpacing: '-0.5px',
                        lineHeight: 1.2,
                    }}>
                        Welcome Back
                    </h1>
                    <p style={{ margin: 0, fontSize: '14px', color: '#9ca3af', lineHeight: 1.6 }}>
                        Sign in to grant permissions.
                    </p>
                </div>

                {/* Google Sign-In Button */}
                <button
                    id="google-login-btn"
                    onClick={handleGoogleLogin}
                    disabled={loading}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '100%',
                        padding: '12px 20px',
                        fontSize: '14px',
                        fontWeight: 600,
                        color: '#111827',
                        background: loading ? '#e5e7eb' : '#ffffff',
                        border: 'none',
                        borderRadius: '12px',
                        cursor: loading ? 'wait' : 'pointer',
                        pointerEvents: 'auto',   /* override parent cursor:none */
                        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                        opacity: loading ? 0.7 : 1,
                    }}
                    onMouseEnter={e => {
                        (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)';
                        (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 24px rgba(0,0,0,0.4)';
                    }}
                    onMouseLeave={e => {
                        (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
                        (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)';
                    }}
                >
                    <svg style={{ width: '20px', height: '20px', marginRight: '12px', flexShrink: 0 }} viewBox="0 0 48 48">
                        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
                        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
                        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
                        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
                    </svg>
                    Continue with Google
                </button>

                <p style={{ marginTop: '24px', textAlign: 'center', fontSize: '12px', color: '#6b7280' }}>
                    Secure authentication powered by Google Workspace.
                    Copy Right Reserved @2026
                </p>

                {/* Continue as Existing Session Button */}
                <button
                    onClick={() => {
                        if (sessionData) {
                            window.location.href = '/dashboard';
                        }
                    }}
                    disabled={!sessionData}
                    style={{
                        marginTop: '16px',
                        display: 'block',
                        width: '100%',
                        padding: '10px 16px',
                        textAlign: 'center',
                        fontSize: '13px',
                        fontWeight: 600,
                        color: sessionData ? '#ffffff' : '#6b7280',
                        background: sessionData ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                        border: sessionData ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '8px',
                        cursor: sessionData ? 'pointer' : 'not-allowed',
                        opacity: sessionData ? 1 : 0.4,
                        pointerEvents: 'auto',
                        transition: 'all 0.2s ease',
                    }}
                    onMouseEnter={e => {
                        if (sessionData) {
                            (e.currentTarget as HTMLButtonElement).style.background = 'rgba(16, 185, 129, 0.3)';
                        }
                    }}
                    onMouseLeave={e => {
                        if (sessionData) {
                            (e.currentTarget as HTMLButtonElement).style.background = 'rgba(16, 185, 129, 0.2)';
                        }
                    }}
                >
                    {sessionData ? `Continue as ${sessionData.name || sessionData.email}` : 'No Active Local Session'}
                </button>

                {onLogout && sessionData && (
                    <button
                        onClick={onLogout}
                        style={{
                            marginTop: '16px',
                            display: 'block',
                            width: '100%',
                            textAlign: 'center',
                            fontSize: '12px',
                            color: '#fca5a5',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                            pointerEvents: 'auto',
                        }}
                    >
                        Clear Session / Switch User
                    </button>
                )}
            </div>
        </div>
    );
}