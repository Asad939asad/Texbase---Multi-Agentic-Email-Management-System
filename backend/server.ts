import express from 'express';
import type { Request, Response } from 'express';
import { google } from 'googleapis';
import fs from 'fs';
import 'dotenv/config';
import path from 'path';
import { spawnSync, spawn } from 'child_process';
import multer from 'multer';
import sqlite3 from 'sqlite3'; // <-- ADDED: SQLite import

const app = express();
app.use(express.json()); // Added to parse JSON bodies
app.use((_req: Request, res: Response, next: () => void) => {
    console.log(`[${new Date().toISOString()}] ${_req.method} ${_req.url}`);
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS, DELETE');
    res.header('Access-Control-Allow-Headers', 'Content-Type');
    if (_req.method === 'OPTIONS') { res.status(200).end(); return; }
    next();
});

console.log('Backend Started !!!');
// ── Configuration ─────────────────────────────────────────────────────────────
const PORT = 8000;
const FRONTEND_URL = 'http://localhost:5173';
const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || path.resolve(process.cwd(), '..');
const PYTHON_EXE = process.env.PYTHON_EXE || path.join(WORKSPACE_ROOT, 'qwen_env/bin/python3');
const PYTHON_DIR = path.resolve(WORKSPACE_ROOT, 'AgenticControl');
const CHECK_USER_CLI = path.join(PYTHON_DIR, 'check_user_cli.py');
const SAVE_USER_CLI = path.join(PYTHON_DIR, 'save_user_cli.py');
const UPDATE_EMAIL_CLI = path.join(PYTHON_DIR, 'update_email_cli.py');
const UPDATE_METADATA_CLI = path.join(PYTHON_DIR, 'update_client_email.py');
const EMAIL_GENERATOR_CLI = path.join(PYTHON_DIR, 'EmailGenerator.py');
const REVIEW_AGENT_CLI = path.join(PYTHON_DIR, 'ReviewAndHeaderAgent.py');
const MOVE_EMAIL_CLI = path.join(PYTHON_DIR, 'Send_email_db.py');
const APPROVE_FOLLOWUP_CLI = path.join(PYTHON_DIR, 'approve_followup_db.py');
const SEND_EMAIL_CLI = path.join(PYTHON_DIR, 'send_and_move_email_cli.py');
const SEND_FOLLOWUP_CLI = path.join(PYTHON_DIR, 'send_and_move_followup_cli.py');
const GENERATE_FOLLOWUP_CLI = path.join(PYTHON_DIR, 'Handling_FollowUp.py');
const PROCESS_EXCEL_CLI = path.join(PYTHON_DIR, 'process_excel_cli.py');
const READ_INBOX_CLI = path.join(PYTHON_DIR, 'read_inbox.py');
const DRAFT_REPLY_CLI = path.join(PYTHON_DIR, 'draft_reply.py');
const EXCEL_PROCESSOR_CLI = path.join(PYTHON_DIR, 'Excel_Processor.py');

// Send switch — persisted as a tiny JSON file next to database.json
const SWITCH_FILE = path.resolve('send_switch.json');

function getSendSwitch(): boolean {
    try {
        if (!fs.existsSync(SWITCH_FILE)) return false;
        const raw = JSON.parse(fs.readFileSync(SWITCH_FILE, 'utf-8'));
        return raw.enabled === true;
    } catch { return false; }
}

function setSendSwitch(enabled: boolean) {
    fs.writeFileSync(SWITCH_FILE, JSON.stringify({ enabled, updated_at: new Date().toISOString() }, null, 2));
    console.log(`[SendSwitch] Email sending ${enabled ? 'ENABLED' : 'DISABLED'}`);
}


// Database paths
const DB_TRACKING = path.join(WORKSPACE_ROOT, 'Database/EmailsUnderReview/emailsUnderReview.db');
const DB_FOLLOWUP_REVIEW = path.join(WORKSPACE_ROOT, 'Database/EmailsUnderReview/followups_under_review.db');
const RE_TRACKING = path.join(WORKSPACE_ROOT, 'Database/EmailsSent/email_to_be_sent.db');
const DB_FOLLOWUP_SENT = path.join(WORKSPACE_ROOT, 'Database/EmailsSent/followups_sent.db');
const DB_FOLLOWUPS_JOURNEY = path.join(WORKSPACE_ROOT, 'Database/FollowUps/sent_emails.db');
const DB_INBOX = path.join(WORKSPACE_ROOT, 'Database/Inbox/inbox.db');

// ── Shared DB connection for testing / debugging ──────────────────────────────
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID || '';
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET || '';
const GOOGLE_REDIRECT_URI = process.env.GOOGLE_REDIRECT_URI || 'http://localhost:8000/api/auth/google/callback';

// ── Session storage (JSON file) ───────────────────────────────────────────────
const DB_FILE = path.resolve('database.json');

function saveToDatabase(tokens: any, userInfo: { name: string; email: string }) {
    const data = {
        user_id: userInfo.email,
        name: userInfo.name,
        email: userInfo.email,
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        updated_at: new Date().toISOString(),
    };
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
    console.log(`💾 Session saved: ${userInfo.name} <${userInfo.email}>`);
}

function readSession() {
    try {
        if (!fs.existsSync(DB_FILE)) return null;
        const d = JSON.parse(fs.readFileSync(DB_FILE, 'utf-8'));
        return d.email ? d : null;
    } catch { return null; }
}

// ── Python bridge helpers ─────────────────────────────────────────────────────
function getPythonSpawnOptions(extraEnv: Record<string, string> = {}) {
    return {
        cwd: WORKSPACE_ROOT,
        env: {
            ...process.env,
            WORKSPACE_ROOT: WORKSPACE_ROOT,
            PYTHONPATH: [
                path.join(WORKSPACE_ROOT, 'src_2', 'ColdEmail'),
                path.join(WORKSPACE_ROOT, 'AgenticControl'),
                path.join(WORKSPACE_ROOT, 'USA_ImportYeti'),
                process.env.PYTHONPATH || ''
            ].filter(Boolean).join(':'),
            ...extraEnv
        }
    };
}
function checkUserExists(email: string): boolean {
    const result = spawnSync(PYTHON_EXE, [CHECK_USER_CLI, email], { encoding: 'utf-8' });
    if (result.error) { console.error('Python check error:', result.error); return false; }
    try {
        const out = JSON.parse(result.stdout.trim());
        console.log(`🐍 check_user_exists(${email}) →`, out.exists);
        return out.exists === true;
    } catch { return false; }
}

// Async wrapper — spawns python3 without blocking the Node.js event loop.
// Resolves immediately when Python prints a valid JSON response (e.g. {"ok": true})
function saveUserProfileViaPython(payload: object): Promise<{ ok: boolean; error?: string }> {
    return new Promise((resolve) => {
        console.log(`[ProfileSave] Spawning ${PYTHON_EXE} save_user_cli.py (async)...`);
        const child = spawn(PYTHON_EXE, [SAVE_USER_CLI], getPythonSpawnOptions());

        let stdout = '';
        let stderr = '';
        let resolved = false;

        child.stdin.write(JSON.stringify(payload));
        child.stdin.end();

        child.stdout.on('data', (d: Buffer) => {
            stdout += d.toString();
            // Try to parse the JSON as soon as we get it
            try {
                const parsed = JSON.parse(stdout.trim());
                if (!resolved) {
                    resolved = true;
                    console.log('[ProfileSave] Received JSON response from Python, resolving early.');
                    resolve(parsed);
                }
            } catch (e) {
                // Not yet complete JSON, wait for more data
            }
        });

        child.stderr.on('data', (d: Buffer) => {
            const line = d.toString().trim();
            if (line) console.log('[ProfileSave|py]', line);
            stderr += line;
        });

        child.on('close', (code: number | null, signal: string | null) => {
            console.log(`[ProfileSave] Python exited — code=${code} signal=${signal}`);
            if (!resolved) {
                resolved = true;
                const raw = stdout.trim();
                if (!raw) {
                    resolve({ ok: false, error: stderr || 'Python produced no output' });
                    return;
                }
                try {
                    resolve(JSON.parse(raw));
                } catch {
                    console.error('[ProfileSave] Could not parse Python stdout:', raw);
                    resolve({ ok: false, error: stderr || raw });
                }
            }
        });

        child.on('error', (err: Error) => {
            console.error('[ProfileSave] spawn error:', err);
            if (!resolved) {
                resolved = true;
                resolve({ ok: false, error: err.message });
            }
        });
    });
}

// ── Generic async Python CLI helper ────────────────────────────────────────────
// Spawns a python process with JSON via stdin, returns parsed JSON from stdout.
export async function runPythonCli(scriptPath: string, payload: any, tag = 'PyCLI'): Promise<any> {
    return new Promise((resolve) => {
        const child = spawn(PYTHON_EXE, [scriptPath], getPythonSpawnOptions());
        let stdout = '';
        let stderr = '';
        let resolved = false;

        child.stdin.write(JSON.stringify(payload));
        child.stdin.end();

        child.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
        child.stderr.on('data', (d: Buffer) => {
            const line = d.toString().trim();
            if (line) console.log(`[${tag}|py]`, line);
            stderr += line;
        });

        child.on('close', (code) => {
            if (resolved) return;
            resolved = true;
            const raw = stdout.trim();
            // Find last JSON line (scripts may print log lines before the JSON)
            const lines = raw.split('\n').reverse();
            for (const line of lines) {
                try { resolve(JSON.parse(line)); return; } catch { /* skip */ }
            }
            resolve({ ok: false, error: stderr || raw || `Process exited with code ${code}` });
        });

        child.on('error', (err: Error) => {
            if (!resolved) { resolved = true; resolve({ ok: false, error: err.message }); }
        });
    });
}

// Alias for compatibility
export const runPythonJSON = runPythonCli;

// multer — store uploaded CV in memory so we can base64-encode it for Python
const upload = multer({ storage: multer.memoryStorage() });

// ── ROUTE: Save profile (called when user completes ProfilePage) ───────────────
app.post('/api/profile/save',
    upload.single('cv_file'),           // 'cv_file' = form field name
    async (req: Request, res: Response) => {
        console.log('[ProfileSave] POST /api/profile/save received');

        try {
            const session = readSession();
            if (!session) { res.status(401).json({ error: 'Not authenticated' }); return; }

            const { name, location, github_description, languages } = req.body;
            const cvFile = (req as any).file as Express.Multer.File | undefined;

            const payload = {
                email: session.email,
                name: name || session.name,
                location: location || '',
                github_description: github_description || '',
                languages: JSON.parse(languages || '[]'),
                cv_file_b64: cvFile ? cvFile.buffer.toString('base64') : '',
                cv_filename: cvFile ? cvFile.originalname : '',
                access_token: session.access_token || '',
                refresh_token: session.refresh_token || '',
            };

            console.log('[ProfileSave] Saving profile for:', session.email, '| cv:', cvFile?.originalname ?? 'none');
            const result = await saveUserProfileViaPython(payload);   // ← non-blocking now

            if (result.ok) {
                res.json({ ok: true });
            } else {
                console.error('[ProfileSave] Python error:', result.error);
                res.status(500).json({ error: result.error });
            }
        } catch (err) {
            console.error('[ProfileSave] Unexpected error:', err);
            res.status(500).json({ error: 'Failed to save profile' });
        }
    }
);



// ── ROUTE: Upload Excel (called from Dashboard/Profile) ───────────────
app.post('/api/upload-excel',
    upload.single('excel_file'),
    (req: Request, res: Response) => {
        console.log('[ExcelUpload] POST /api/upload-excel received');

        try {
            const file = req.file;
            if (!file) {
                res.status(400).json({ error: 'No file uploaded' });
                return;
            }

            // Save file to a temporary location
            const tempFilePath = path.join('/tmp', `excel_upload_${Date.now()}_${file.originalname}`);
            fs.writeFileSync(tempFilePath, file.buffer);
            console.log(`[ExcelUpload] Saved file to ${tempFilePath}, spawning process_excel_cli.py...`);

            const child = spawn(PYTHON_EXE, [PROCESS_EXCEL_CLI, tempFilePath], getPythonSpawnOptions());

            child.stdout.on('data', (d: Buffer) => {
                console.log(`[ExcelUpload|py] ${d.toString().trim()}`);
            });
            child.stderr.on('data', (d: Buffer) => {
                console.log(`[ExcelUpload|err] ${d.toString().trim()}`);
            });
            child.on('close', (code) => {
                console.log(`[ExcelUpload] Python finished with code ${code}`);
            });

            // Immediately respond to the client so UI doesn't hang
            res.json({ ok: true, message: "Excel uploaded and processing started in background." });

        } catch (err) {
            console.error('[ExcelUpload] Error:', err);
            res.status(500).json({ error: 'Failed to upload excel file' });
        }
    }
);


let pipelineStatus = {
    active: false,
    startedAt: null as string | null,
    lastExitCode: null as number | null
};

// ── ROUTE: Run Excel Processor Pipeline ──────────────────────────────
app.post('/api/pipeline/run-excel', (req: Request, res: Response) => {
    if (pipelineStatus.active) {
        res.status(400).json({ error: 'Pipeline is already running' });
        return;
    }

    console.log('\n' + '═'.repeat(60));
    console.log('🚀 [PIPELINE] RECEIVED TRIGGER FROM FRONTEND');
    console.log(`📂 Script: ${EXCEL_PROCESSOR_CLI}`);
    console.log(`📂 Backend CWD: ${process.cwd()}`);
    console.log(`📂 Python: ${PYTHON_EXE}`);
    console.log('═'.repeat(60));

    pipelineStatus.active = true;
    pipelineStatus.startedAt = new Date().toISOString();
    pipelineStatus.lastExitCode = null;

    try {
        const child = spawn(PYTHON_EXE, [EXCEL_PROCESSOR_CLI], getPythonSpawnOptions());

        child.stdout.on('data', (d: Buffer) => {
            console.log(`[ExcelProcessor|out] ${d.toString().trim()}`);
        });

        child.stderr.on('data', (d: Buffer) => {
            console.error(`[ExcelProcessor|err] ${d.toString().trim()}`);
        });

        child.on('error', (err) => {
            console.error('❌ [PIPELINE] Failed to start process:', err);
            pipelineStatus.active = false;
        });

        child.on('close', (code) => {
            console.log(`\n✅ [PIPELINE] Finished with code ${code}`);
            pipelineStatus.active = false;
            pipelineStatus.lastExitCode = code;
        });

        res.json({ ok: true, message: "Excel Processor pipeline started." });
    } catch (err) {
        console.error('❌ [PIPELINE] Unexpected error:', err);
        pipelineStatus.active = false;
        res.status(500).json({ error: 'Failed to start pipeline' });
    }
});

app.get('/api/pipeline/status', (req: Request, res: Response) => {
    res.json(pipelineStatus);
});

// ── Google OAuth2 client ──────────────────────────────────────────────────────
const oauth2Client = new google.auth.OAuth2(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI);

const SCOPES = [//later to be added more
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/calendar',
];

// ── ROUTE: Get Google Auth URL ────────────────────────────────────────────────
app.get('/api/auth/google', (_req: Request, res: Response) => {
    try {
        const url = oauth2Client.generateAuthUrl({ access_type: 'offline', prompt: 'consent', scope: SCOPES });
        res.json({ url });
    } catch (err) {
        res.status(500).json({ error: 'Failed to generate auth URL' });
    }
});

// ── ROUTE: Session check ──────────────────────────────────────────────────────
app.get('/api/auth/session', (_req: Request, res: Response) => {
    const s = readSession();
    if (!s) { res.status(404).json({ error: 'No session' }); return; }
    res.json({ name: s.name, email: s.email });
});

// ── ROUTE: Logout ─────────────────────────────────────────────────────────────
app.get('/api/auth/logout', (_req: Request, res: Response) => {
    fs.writeFileSync(DB_FILE, '{}');
    res.json({ ok: true });
});

// ── ROUTE: Check if registered in SQLite ─────────────────────────────────────
app.get('/api/auth/check-registered', (req: Request, res: Response) => {
    const email = req.query.email as string | undefined;
    if (!email) { res.status(400).json({ error: 'Missing email' }); return; }
    const registered = checkUserExists(email);
    res.json({ registered });
});

// ── ROUTE: Google OAuth callback ──────────────────────────────────────────────
app.get('/api/auth/google/callback', async (req: Request, res: Response) => {
    const code = req.query.code as string | undefined;
    if (!code) { res.status(400).send('Missing authorization code.'); return; }

    try {
        // 1. Exchange code → tokens
        const { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens);

        // 2. Get name + email from Google
        const oauth2 = google.oauth2({ version: 'v2', auth: oauth2Client });
        const { data: userInfo } = await oauth2.userinfo.get();
        const name = userInfo.name ?? 'Unknown';
        const email = userInfo.email ?? '';
        console.log(`👤 Google user: ${name} <${email}>`);

        // 3. Save session (tokens + identity)
        saveToDatabase(tokens, { name, email });

        // 4. ── KEY DECISION: does this user exist in the SQL DB? ──────────────
        const alreadyRegistered = checkUserExists(email);

        const params = new URLSearchParams({ name, email });

        if (alreadyRegistered) {
            // Returning user → /dashboard
            console.log(`✅ Returning user detected → redirecting to /dashboard`);
            params.set('page', 'dashboard');
        } else {
            // New user → /profile (collect their details)
            console.log(`🆕 New user detected → redirecting to /profile`);
            params.set('page', 'profile');
        }

        res.redirect(`${FRONTEND_URL}?google_connected=true&${params.toString()}`);

    } catch (err) {
        console.error('❌ OAuth callback error:', err);
        res.redirect(`${FRONTEND_URL}?google_connected=false`);
    }
});

// ── ROUTE: Save profile (called when user completes ProfilePage) ───────────────
app.post('/api/profile/save',
    upload.single('cv_file'),           // 'cv_file' = form field name
    async (req: Request, res: Response) => {
        console.log("Reached server.ts")

        try {
            const session = readSession();
            if (!session) { res.status(401).json({ error: 'Not authenticated' }); return; }

            const { name, location, github_description, languages } = req.body;
            const cvFile = (req as any).file as Express.Multer.File | undefined;

            const payload = {
                email: session.email,
                name: name || session.name,
                location: location || '',
                github_description: github_description || '',
                languages: JSON.parse(languages || '[]'),
                cv_file_b64: cvFile ? cvFile.buffer.toString('base64') : '',
                cv_filename: cvFile ? cvFile.originalname : '',
                access_token: session.access_token || '',
                refresh_token: session.refresh_token || '',
            };

            console.log('💾 Saving profile for:', session.email);
            const result = await saveUserProfileViaPython(payload);

            if (result.ok) {
                res.json({ ok: true });
            } else {
                console.error('Python save error:', result.error);
                res.status(500).json({ error: result.error });
            }
        } catch (err) {
            console.error('❌ Profile save error:', err);
            res.status(500).json({ error: 'Failed to save profile' });
        }
    }
);

// ── ROUTE: Get Tracking Dashboard Data ────────────────────────────────────────
// <-- ADDED: This replaces your Flask server
app.get('/api/tracking', (req: Request, res: Response) => {
    if (!fs.existsSync(DB_TRACKING)) {
        res.status(404).json({ error: 'Database not found' });
        return;
    }

    // Open the SQLite database in Read-Only mode
    const db = new sqlite3.Database(DB_TRACKING, sqlite3.OPEN_READONLY, (err) => {
        if (err) {
            console.error('Database open error:', err);
            res.status(500).json({ error: 'Failed to connect to database' });
            return;
        }
    });

    // Fetch all records, newest first
    db.all('SELECT * FROM tracking ORDER BY timestamp DESC', [], (err, rows) => {
        if (err) {
            console.error('Database query error:', err);
            res.status(500).json({ error: 'Failed to query database' });
        } else {
            res.json(rows);
        }

        // Close the database connection
        db.close();
    });
});

// ── ROUTE: Get Ready to send Tracking Dashboard Data ────────────────────────────────────────

app.get('/api/tracking_ready_to_send', (req: Request, res: Response) => {
    if (!fs.existsSync(RE_TRACKING)) {
        res.status(404).json({ error: 'Database not found' });
        return;
    }

    // Open the SQLite database in Read-Only mode
    const db = new sqlite3.Database(RE_TRACKING, sqlite3.OPEN_READONLY, (err) => {
        if (err) {
            console.error('Database open error:', err);
            res.status(500).json({ error: 'Failed to connect to database' });
            return;
        }
    });

    // Fetch all records, newest first
    db.all('SELECT * FROM ready_emails ORDER BY timestamp DESC', [], (err, rows) => {
        if (err) {
            console.error('Database query error:', err);
            res.status(500).json({ error: 'Failed to query database' });
        } else {
            res.json(rows);
        }

        // Close the database connection
        db.close();
    });
});

// ── ROUTE: Get Single Tracking Record ─────────────────────────────────────────
app.get('/api/tracking/:id', (req: Request, res: Response) => {
    const id = req.params.id;
    if (!fs.existsSync(DB_TRACKING)) {
        res.status(404).json({ error: 'Database not found' });
        return;
    }

    const db = new sqlite3.Database(DB_TRACKING, sqlite3.OPEN_READONLY, (err) => {
        if (err) {
            console.error('Database open error:', err);
            res.status(500).json({ error: 'Failed to connect to database' });
            return;
        }
    });

    db.get('SELECT * FROM tracking WHERE id = ?', [id], (err, row) => {
        if (err) {
            console.error('Database query error:', err);
            res.status(500).json({ error: 'Failed to query database' });
        } else if (!row) {
            res.status(404).json({ error: 'Record not found' });
        } else {
            res.json(row);
        }
        db.close();
    });
});

// ── ROUTE: Save Email Manually ────────────────────────────────────────────────
app.put('/api/tracking/:id/save', (req: Request, res: Response) => {
    const id = req.params.id;
    const { new_content, subject } = req.body;

    if (!new_content) {
        res.status(400).json({ error: 'Missing new_content' });
        return;
    }

    const db = new sqlite3.Database(DB_TRACKING, sqlite3.OPEN_READWRITE, (err) => {
        if (err) {
            console.error('Database open error:', err);
            res.status(500).json({ error: 'Failed to connect to database' });
            return;
        }
    });

    db.get('SELECT body_json FROM tracking WHERE id = ?', [id], (err, row: any) => {
        if (err || !row) {
            db.close();
            res.status(404).json({ error: 'Record not found' });
            return;
        }

        try {
            const payload = JSON.parse(row.body_json);
            if (payload.body) payload.body.generated_content = new_content;
            if (payload.body && subject) payload.body.subject = subject;

            const updateQuery = subject
                ? 'UPDATE tracking SET body_json = ?, generated_subject = ? WHERE id = ?'
                : 'UPDATE tracking SET body_json = ? WHERE id = ?';
            const params = subject
                ? [JSON.stringify(payload), subject, id]
                : [JSON.stringify(payload), id];

            db.run(updateQuery, params, function (err) {
                if (err) {
                    res.status(500).json({ error: 'Failed to update database' });
                } else {
                    res.json({ ok: true });
                }
                db.close();
            });
        } catch (e) {
            db.close();
            res.status(500).json({ error: 'JSON parsing error in DB' });
        }
    });
});

// ── ROUTE: Update Tracking Status ─────────────────────────────────────────────
app.put('/api/tracking/:id/status', async (req: Request, res: Response) => {
    const id = req.params.id;
    const { status } = req.body;

    if (status.toLowerCase() === 'approved') {
        try {
            const out = await runPythonCli(MOVE_EMAIL_CLI, { id }, 'MoveEmail');
            return res.json(out);
        } catch (e) {
            return res.status(500).json({ ok: false, error: String(e) });
        }
    }

    if (!status) return res.status(400).json({ error: 'Status is required' });

    const db = new sqlite3.Database(DB_TRACKING);
    db.run('UPDATE tracking SET status = ? WHERE id = ?', [status, id], function (err) {
        if (err) {
            res.status(500).json({ error: 'Failed to update status' });
        } else {
            res.json({ ok: true });
        }
        db.close();
    });
});

// ── ROUTE: Merged Review Queue (cold + followup) ──────────────────────────────
// Returns all pending items from both DBs with a `type` field ('cold' | 'followup')
app.get('/api/review/all', (_req: Request, res: Response) => {
    const coldExists = fs.existsSync(DB_TRACKING);
    const followupExists = fs.existsSync(DB_FOLLOWUP_REVIEW);

    let coldRows: any[] = [];
    let followupRows: any[] = [];
    let pending = 0;

    const finish = () => {
        if (pending > 0) return;
        const merged = [
            ...coldRows.map(r => ({ ...r, type: 'cold' })),
            ...followupRows.map(r => ({ ...r, type: 'followup' })),
        ].sort((a, b) => {
            const ta = a.timestamp || a.followup_date || '';
            const tb = b.timestamp || b.followup_date || '';
            return tb.localeCompare(ta);
        });
        res.json(merged);
    };

    if (coldExists) {
        pending++;
        const db = new sqlite3.Database(DB_TRACKING, sqlite3.OPEN_READONLY);
        db.all('SELECT * FROM tracking ORDER BY timestamp DESC', [], (err, rows) => {
            if (!err) coldRows = rows as any[];
            db.close();
            pending--;
            finish();
        });
    }

    if (followupExists) {
        pending++;
        const db = new sqlite3.Database(DB_FOLLOWUP_REVIEW, sqlite3.OPEN_READONLY);
        db.all('SELECT * FROM followups_pending ORDER BY followup_date DESC', [], (err, rows) => {
            if (!err) followupRows = rows as any[];
            db.close();
            pending--;
            finish();
        });
    }

    if (!coldExists && !followupExists) {
        res.json([]);
    } else if (pending === 0) {
        finish();
    }
});

// ── ROUTE: Send switch — GET current state ────────────────────────────────────
app.get('/api/settings/send-switch', (_req: Request, res: Response) => {
    res.json({ enabled: getSendSwitch() });
});

// ── ROUTE: Send switch — toggle ON/OFF ────────────────────────────────────────
app.post('/api/settings/send-switch', (req: Request, res: Response) => {
    const { enabled } = req.body;
    if (typeof enabled !== 'boolean') {
        res.status(400).json({ error: 'Body must be { "enabled": true|false }' });
        return;
    }
    setSendSwitch(enabled);
    res.json({ ok: true, enabled });
});

// ── ROUTE: Approve cold email ─────────────────────────────────────────────────
app.put('/api/review/cold/:id/approve', async (req: Request, res: Response) => {
    const id = req.params.id;

    // Check if email is 'not updated' before approving
    const db = new sqlite3.Database(DB_TRACKING, sqlite3.OPEN_READONLY);
    const row: any = await new Promise((resolve) => {
        db.get('SELECT company_email FROM tracking WHERE id = ?', [id], (err, r) => resolve(r));
    });
    db.close();

    if (row && row.company_email === 'not updated') {
        return res.status(400).json({ ok: false, code: 'EMAIL_REQUIRED', message: 'Recipient email is missing. Please provide one.' });
    }

    const cli = getSendSwitch() ? SEND_EMAIL_CLI : MOVE_EMAIL_CLI;
    console.log(`[Approve Cold] id=${id} sendSwitch=${getSendSwitch()} cli=${path.basename(cli)}`);
    try {
        const out = await runPythonCli(cli, { id: parseInt(id as string) }, 'ApproveCold');
        return res.json(out);
    } catch (e) {
        return res.status(500).json({ ok: false, error: String(e) });
    }
});


// ── ROUTE: Reject cold email ──────────────────────────────────────────────────
app.put('/api/review/cold/:id/reject', (req: Request, res: Response) => {
    const id = req.params.id;
    const db = new sqlite3.Database(DB_TRACKING);
    db.run('UPDATE tracking SET status = ? WHERE id = ?', ['rejected', id], function (err) {
        if (err) res.status(500).json({ error: 'Failed to update status' });
        else res.json({ ok: true });
        db.close();
    });
});

// ── ROUTE: Get single follow-up record (for editor) ───────────────────────────
app.get('/api/review/followup/:id', (req: Request, res: Response) => {
    const id = req.params.id;
    if (!fs.existsSync(DB_FOLLOWUP_REVIEW)) {
        res.status(404).json({ error: 'Follow-up database not found' });
        return;
    }
    const db = new sqlite3.Database(DB_FOLLOWUP_REVIEW, sqlite3.OPEN_READONLY);
    db.get('SELECT * FROM followups_pending WHERE id = ?', [id], (err, row) => {
        if (err) res.status(500).json({ error: 'Query failed' });
        else if (!row) res.status(404).json({ error: 'Record not found' });
        else res.json(row);
        db.close();
    });
});

// ── ROUTE: Save follow-up edits ───────────────────────────────────────────────
app.put('/api/review/followup/:id/save', (req: Request, res: Response) => {
    const id = req.params.id;
    const { new_content, subject } = req.body;
    if (!new_content) { res.status(400).json({ error: 'Missing new_content' }); return; }

    const db = new sqlite3.Database(DB_FOLLOWUP_REVIEW, sqlite3.OPEN_READWRITE);
    db.get('SELECT body_json FROM followups_pending WHERE id = ?', [id], (err, row: any) => {
        if (err || !row) { db.close(); res.status(404).json({ error: 'Record not found' }); return; }
        try {
            const payload = JSON.parse(row.body_json);
            if (payload.body) payload.body.generated_content = new_content;
            if (payload.body && subject) payload.body.subject = subject;

            const updateQuery = subject
                ? 'UPDATE followups_pending SET body_json = ?, generated_subject = ? WHERE id = ?'
                : 'UPDATE followups_pending SET body_json = ? WHERE id = ?';
            const params = subject
                ? [JSON.stringify(payload), subject, id]
                : [JSON.stringify(payload), id];

            db.run(updateQuery, params, function (err2) {
                if (err2) res.status(500).json({ error: 'Failed to save' });
                else res.json({ ok: true });
                db.close();
            });
        } catch {
            db.close();
            res.status(500).json({ error: 'JSON parse error' });
        }
    });
});

// ── ROUTE: Approve follow-up ──────────────────────────────────────────────────
app.put('/api/review/followup/:id/approve', async (req: Request, res: Response) => {
    const id = req.params.id;

    // Check if email is 'not updated' before approving
    const db = new sqlite3.Database(DB_FOLLOWUP_REVIEW, sqlite3.OPEN_READONLY);
    const row: any = await new Promise((resolve) => {
        db.get('SELECT company_email FROM followups_pending WHERE id = ?', [id], (err, r) => resolve(r));
    });
    db.close();

    if (row && row.company_email === 'not updated') {
        return res.status(400).json({ ok: false, code: 'EMAIL_REQUIRED', message: 'Recipient email is missing. Please provide one.' });
    }

    const cli = getSendSwitch() ? SEND_FOLLOWUP_CLI : APPROVE_FOLLOWUP_CLI;
    console.log(`[Approve Followup] id=${id} sendSwitch=${getSendSwitch()} cli=${path.basename(cli)}`);
    try {
        const out = await runPythonCli(cli, { id: parseInt(id as string) }, 'ApproveFollowup');
        return res.json(out);
    } catch (e) {
        return res.status(500).json({ ok: false, error: String(e) });
    }
});


// ── ROUTE: Reject follow-up ───────────────────────────────────────────────────
app.put('/api/review/followup/:id/reject', (_req: Request, res: Response) => {
    const id = _req.params.id;
    const db = new sqlite3.Database(DB_FOLLOWUP_REVIEW, sqlite3.OPEN_READWRITE);
    db.run('UPDATE followups_pending SET status = ? WHERE id = ?', ['rejected', id], function (err) {
        if (err) res.status(500).json({ error: 'Failed to update status' });
        else res.json({ ok: true });
        db.close();
    });
});

// ── ROUTE: Delete cold email record ──────────────────────────────────────────
app.delete('/api/review/cold/:id', (req: Request, res: Response) => {
    const id = req.params.id;
    const db = new sqlite3.Database(DB_TRACKING);
    db.run('DELETE FROM tracking WHERE id = ?', [id], function (err) {
        if (err) res.status(500).json({ error: 'Failed to delete record' });
        else res.json({ ok: true });
        db.close();
    });
});

// ── ROUTE: Delete follow-up record ───────────────────────────────────────────
app.delete('/api/review/followup/:id', (req: Request, res: Response) => {
    const id = req.params.id;
    const db = new sqlite3.Database(DB_FOLLOWUP_REVIEW);
    db.run('DELETE FROM followups_pending WHERE id = ?', [id], function (err) {
        if (err) res.status(500).json({ error: 'Failed to delete record' });
        else res.json({ ok: true });
        db.close();
    });
});

// ── ROUTE: Journey — all sent cold emails (FollowUps/sent_emails.db) ──────────
app.get('/api/followups/journey', (_req: Request, res: Response) => {
    if (!fs.existsSync(DB_FOLLOWUPS_JOURNEY)) {
        res.json([]);
        return;
    }
    const db = new sqlite3.Database(DB_FOLLOWUPS_JOURNEY, sqlite3.OPEN_READONLY);
    // Use date_sent as the primary sort key (date_applied is legacy)
    db.all('SELECT * FROM sent_applications ORDER BY date_sent DESC', [], (err, rows) => {
        if (err) {
            console.error('❌ [JourneyAPI] DB Error:', err);
            res.status(500).json({ error: 'Query failed' });
        } else {
            res.json(rows);
        }
        db.close();
    });
});

// ── ROUTE: Sent approved follow-ups (EmailsSent/followups_sent.db) ─────────────
app.get('/api/followups/sent-approved', (_req: Request, res: Response) => {
    if (!fs.existsSync(DB_FOLLOWUP_SENT)) {
        res.json([]);
        return;
    }
    const db = new sqlite3.Database(DB_FOLLOWUP_SENT, sqlite3.OPEN_READONLY);
    db.all('SELECT * FROM sent_followups ORDER BY approved_at DESC', [], (err, rows) => {
        if (err) {
            console.error('❌ [SentApprovedAPI] DB Error:', err);
            res.status(500).json({ error: 'Query failed' });
        } else {
            res.json(rows);
        }
        db.close();
    });
});


// ── ROUTE: Inbox API ─────────────────────────────────────────────────────────

app.get('/api/inbox', (req: Request, res: Response) => {
    if (!fs.existsSync(DB_INBOX)) {
        res.json([]);
        return;
    }
    const db = new sqlite3.Database(DB_INBOX, sqlite3.OPEN_READONLY);
    db.all('SELECT * FROM inbox_threads ORDER BY date_received DESC', [], (err, rows) => {
        if (err) {
            console.error('❌ [InboxAPI] DB Error:', err);
            res.status(500).json({ error: 'Query failed' });
        } else {
            res.json(rows);
        }
        db.close();
    });
});

// ── ROUTE: PO Quotation Processing ──────────────────────────────────────────────
const PO_BASE_DIR = path.join(WORKSPACE_ROOT, 'AgenticControl/PO:Quotation');
const PO_PIPELINE_CLI = path.join(PO_BASE_DIR, 'run_po_pipeline.py');
const PO_PREDICTOR_CLI = path.join(PO_BASE_DIR, 'quotation_predictor.py');
const PO_CWD = PO_BASE_DIR;
const PO_DB_PATH = path.join(PO_BASE_DIR, 'po_database.db');
const PRED_DB_PATH = path.join(PO_BASE_DIR, 'quotation_predictions.db');

const poUpload = multer({
    storage: multer.diskStorage({
        destination: (req, file, cb) => {
            const dir = path.join(WORKSPACE_ROOT, 'backend', 'uploads');
            if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
            cb(null, dir);
        },
        filename: (req, file, cb) => {
            cb(null, Date.now() + '-' + file.originalname.replace(/[^a-zA-Z0-9.-]/g, '_'));
        }
    })
});

app.post('/api/po/process', poUpload.single('file'), (req: Request, res: Response) => {
    if (!req.file) {
        res.status(400).json({ error: 'No file uploaded' });
        return;
    }

    // Reset PO Pipeline State
    poPipelineState = {
        status: 'running',
        phase: 'initializing',
        startedAt: new Date().toISOString(),
        log: [`Upload successful: ${req.file.originalname}`, 'Starting PO analysis pipeline...']
    };

    try {
        const child = spawn(PYTHON_EXE, [PO_PIPELINE_CLI], getPythonSpawnOptions({ PO_CWD: PO_CWD }));
        let stdout = '';
        let stderr = '';

        child.stdin.write(JSON.stringify({ file_path: req.file.path }));
        child.stdin.end();

        child.stdout.on('data', (d: Buffer) => {
            const msg = d.toString();
            stdout += msg;
            addPOLog(msg);
        });

        child.stderr.on('data', (d: Buffer) => {
            const line = d.toString().trim();
            if (line) {
                console.log('[PO_CLI]', line);
                addPOLog(`[stderr] ${line}`);
            }
            stderr += line;
        });

        child.on('close', (code: number | null) => {
            poPipelineState.status = code === 0 ? 'done' : 'error';
            if (code !== 0) addPOLog(`Pipeline exited with code ${code}`);

            try {
                // Find JSON at the end of stdout
                const lines = stdout.trim().split('\n');
                let parsed = null;
                for (let i = lines.length - 1; i >= 0; i--) {
                    if (lines[i].trim().startsWith('{')) {
                        try {
                            parsed = JSON.parse(lines[i].trim());
                            break;
                        } catch (e) { }
                    }
                }

                if (parsed) {
                    addPOLog('Analysis complete. Processing results.');
                    res.json(parsed);
                } else {
                    addPOLog('Error: Failed to parse results from analysis script.');
                    res.status(500).json({ error: 'Failed to parse python output', stderr });
                }
            } catch (e: any) {
                res.status(500).json({ error: e.message });
            }
        });
    } catch (err) {
        poPipelineState.status = 'error';
        addPOLog(`Internal Server Error: ${String(err)}`);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// GET /api/po/pipeline-status
app.get('/api/po/pipeline-status', (_req: Request, res: Response) => {
    res.json(poPipelineState);
});

// GET /api/po/tables - List all tables in po_database.db
app.get('/api/po/tables', (req: Request, res: Response) => {
    if (!fs.existsSync(PO_DB_PATH)) {
        res.status(404).json({ error: 'PO Database not found' });
        return;
    }
    const db = new sqlite3.Database(PO_DB_PATH, sqlite3.OPEN_READONLY);
    db.all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'", (err, rows) => {
        if (err) {
            res.status(500).json({ error: err.message });
        } else {
            res.json({ tables: rows.map((r: any) => r.name) });
        }
        db.close();
    });
});

// GET /api/po/table/:name - Get all rows from a PO table
app.get('/api/po/table/:name', (req: Request, res: Response) => {
    const tableName = req.params.name;
    if (!fs.existsSync(PO_DB_PATH)) {
        res.status(404).json({ error: 'PO Database not found' });
        return;
    }
    const db = new sqlite3.Database(PO_DB_PATH, sqlite3.OPEN_READONLY);
    // Be careful with table names to prevent injection, although here it's likely safe for internal use
    db.all(`SELECT * FROM "${tableName}"`, (err, rows) => {
        if (err) {
            res.status(500).json({ error: err.message });
        } else {
            res.json({ success: true, rows });
        }
        db.close();
    });
});

// GET /api/po/predictions/:name - Get all predictions for a specific PO table
app.get('/api/po/predictions/:name', (req: Request, res: Response) => {
    const tableName = req.params.name;
    const predTableName = `${tableName}_predictions`;
    if (!fs.existsSync(PRED_DB_PATH)) {
        res.status(404).json({ error: 'Prediction Database not found' });
        return;
    }
    const db = new sqlite3.Database(PRED_DB_PATH, sqlite3.OPEN_READONLY);
    // Use a subquery to get only the most recent prediction row for each item_no/description pair
    const query = `
        SELECT * FROM "${predTableName}" 
        WHERE id IN (
            SELECT MAX(id) FROM "${predTableName}"
            GROUP BY item_no, description
        )
        ORDER BY id ASC
    `;
    db.all(query, (err, rows) => {
        if (err) {
            // It might not exist yet, which is fine, just return empty
            res.json({ success: true, predictions: [] });
        } else {
            res.json({ success: true, predictions: rows });
        }
        db.close();
    });
});

// POST /api/po/predict - Run prediction for a specific table
app.post('/api/po/predict', async (req: Request, res: Response) => {
    const { table_name } = req.body;
    if (!table_name) {
        res.status(400).json({ error: 'Missing table_name' });
        return;
    }

    try {
        console.log(`[PO_Predict] Running predictor for table: ${table_name}`);
        // Run the predictor script
        const child = spawn(PYTHON_EXE, [PO_PREDICTOR_CLI, '--table', table_name], getPythonSpawnOptions({ PO_CWD: PO_CWD }));

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
        child.stderr.on('data', (d: Buffer) => {
            const line = d.toString().trim();
            if (line) console.log('[Predictor_CLI]', line);
            stderr += line;
        });

        child.on('close', async (code) => {
            console.log(`[PO_Predict] Predictor finished with code ${code}`);

            // Now fetch the results from quotation_predictions.db
            // The table name in prediction DB is table_name + "_predictions"
            const predTableName = `${table_name}_predictions`;

            if (!fs.existsSync(PRED_DB_PATH)) {
                res.status(500).json({ error: 'Prediction database not found after script execution' });
                return;
            }

            const db = new sqlite3.Database(PRED_DB_PATH, sqlite3.OPEN_READONLY);
            const query = `
                SELECT * FROM "${predTableName}" 
                WHERE id IN (
                    SELECT MAX(id) FROM "${predTableName}"
                    GROUP BY item_no, description
                )
                ORDER BY id ASC
            `;
            db.all(query, (err, rows) => {
                if (err) {
                    res.status(500).json({ error: `Failed to fetch predictions: ${err.message}`, stderr });
                } else {
                    res.json({ success: true, predictions: rows });
                }
                db.close();
            });
        });
    } catch (err: any) {
        res.status(500).json({ error: err.message });
    }
});


app.post('/api/inbox/sync', async (req: Request, res: Response) => {
    try {
        const result = await runPythonCli(READ_INBOX_CLI, {}, 'ReadInbox');
        if (result.error) {
            res.status(500).json({ error: result.error });
        } else {
            res.json({ success: true, new_threads: result.new_threads || [], count: result.fetched_count || 0 });
        }
    } catch (err) {
        console.error('❌ [InboxSync] error:', err);
        res.status(500).json({ error: 'Sync failed' });
    }
});

app.post('/api/inbox/:id/draft', async (req: Request, res: Response) => {
    const id = req.params.id;
    try {
        const result = await runPythonCli(DRAFT_REPLY_CLI, { inbox_id: id }, 'DraftReply');
        if (result.error) {
            res.status(500).json({ error: result.error });
        } else {
            res.json({ success: true });
        }
    } catch (err) {
        console.error('❌ [DraftReply] error:', err);
        res.status(500).json({ error: 'Draft failed' });
    }
});

// 1. Seed oauth2Client with whatever tokens are already in database.json
function seedClientCredentials() {
    const session = readSession();
    if (session?.access_token) {
        oauth2Client.setCredentials({
            access_token: session.access_token,
            refresh_token: session.refresh_token,
        });
        console.log(`🔑 [TokenRefresh] Seeded OAuth2 client with saved tokens (user: ${session.email})`);
    } else {
        console.log(`⚠️  [TokenRefresh] No saved session — skipping credential seed`);
    }
}

// 2. Event-driven: oauth2Client fires 'tokens' whenever Google silently refreshes
//    (e.g. after an API call hits an expired access_token and uses the refresh_token)
function listenForTokenEvents() {
    oauth2Client.on('tokens', (freshTokens) => {
        const session = readSession();
        if (!session) { console.warn('⚠️  [TokenRefresh] tokens event fired but no session on disk'); return; }

        const merged = {
            access_token: freshTokens.access_token ?? session.access_token,
            refresh_token: freshTokens.refresh_token ?? session.refresh_token, // Google only sends a new refresh_token once
        };
        saveToDatabase(merged, { name: session.name, email: session.email });
        console.log(`✅ [TokenRefresh] tokens event — fresh access_token saved to database.json`);
    });
}

// 3. Proactive refresh every 45 min (access tokens last 60 min — we refresh early)
async function proactiveTokenRefresh() {
    const session = readSession();
    if (!session?.refresh_token) {
        console.log(`⚠️  [TokenRefresh] No refresh_token available — proactive refresh skipped`);
        return;
    }

    try {
        // Set credentials so refreshAccessToken() uses the stored refresh_token
        oauth2Client.setCredentials({
            access_token: session.access_token,
            refresh_token: session.refresh_token,
        });

        const { credentials } = await oauth2Client.refreshAccessToken();

        const merged = {
            access_token: credentials.access_token ?? session.access_token,
            refresh_token: credentials.refresh_token ?? session.refresh_token,
        };
        saveToDatabase(merged, { name: session.name, email: session.email });
        console.log(`🔄 [TokenRefresh] Proactive refresh done — database.json updated (${new Date().toISOString()})`);
    } catch (err: any) {
        // invalid_grant = stale refresh token (user re-authenticated elsewhere).
        // Log a short warning instead of the full stack trace — it self-heals on next login.
        const cause = err?.response?.data?.error ?? err?.message ?? String(err);
        if (cause === 'invalid_grant') {
            console.warn(`⚠️  [TokenRefresh] Refresh token expired or revoked (invalid_grant). Re-login to renew.`);
        } else {
            console.error(`❌ [TokenRefresh] Proactive refresh failed:`, err);
        }
    }
}

// ── Start ─────────────────────────────────────────────────────────────────────
// ── ROUTE: Generate Follow-up Now ─────────────────────────────────────────────
app.post('/api/followups/generate/:id', async (req: Request, res: Response) => {
    const id = req.params.id;
    try {
        const out = await runPythonCli(GENERATE_FOLLOWUP_CLI, { id }, 'FollowupGen');
        res.json(out);
    } catch (e) {
        res.status(500).json({ ok: false, error: String(e) });
    }
});


app.listen(PORT, () => {
    console.log(`🚀 Backend Auth Server running on http://localhost:${PORT}`);

    // ── Token lifecycle ──────────────────────────────────────────────────────
    seedClientCredentials();       // load saved tokens into oauth2Client on boot
    listenForTokenEvents();        // write fresh tokens whenever Google auto-refreshes
    proactiveTokenRefresh();       // force a refresh immediately on startup
    setInterval(proactiveTokenRefresh, 2 * 60 * 1000); // then every 45 minutes
    console.log(`⏰ [TokenRefresh] Proactive token refresh scheduled every 45 minutes`);

    // ── Background Agent Runner ──────────────────────────────────────────────
    function runReviewAgent() {
        console.log(`⏱️ Running background task: ${REVIEW_AGENT_CLI}`);
        const agentProcess = spawn(PYTHON_EXE, [REVIEW_AGENT_CLI], getPythonSpawnOptions());

        agentProcess.stdout.on('data', (data) => {
            console.log(`[ReviewAgent] ${data.toString().trim()}`);
        });

        agentProcess.stderr.on('data', (data) => {
            console.error(`[ReviewAgent Error] ${data.toString().trim()}`);
        });

        agentProcess.on('close', (code) => {
            console.log(`[ReviewAgent] Exited with code ${code}`);
        });
    }

    function runOutreachAgent() {
        console.log(`⏱️ Starting background Outreach Agent: ${path.join(PYTHON_DIR, 'OutreachAgent.py')}`);
        // We use spawn (not spawnSync) so it runs as a long-lived process
        const outreachAgent = spawn(PYTHON_EXE, [path.join(PYTHON_DIR, 'OutreachAgent.py')], getPythonSpawnOptions());

        outreachAgent.stdout.on('data', (data) => {
            console.log(`[OutreachAgent] ${data.toString().trim()}`);
        });

        outreachAgent.stderr.on('data', (data) => {
            console.error(`[OutreachAgent Error] ${data.toString().trim()}`);
        });

        outreachAgent.on('close', (code) => {
            console.log(`[OutreachAgent] Process closed with code ${code}. Restarting in 60s...`);
            setTimeout(runOutreachAgent, 60000);
        });
    }

    // Run immediately once on startup
    runReviewAgent();
    runOutreachAgent();

    // Schedule Review Agent (Outreach Agent is self-looping)
    setInterval(runReviewAgent, 1 * 60 * 1000);

    // ── Market Intelligence Scheduler ────────────────────────────────────────
    function runMarketIntelPipeline() {
        if (pipelineState.status === 'running') return;
        console.log('⏰ [SystemClock] Triggering scheduled Market Intelligence run...');
        
        // Use global fetch (available in Node 18+)
        fetch(`http://localhost:${PORT}/api/stats/run-pipeline`, { method: 'POST' }).catch(() => {});
    }

    // Check every minute if it's time to run
    setInterval(() => {
        if (Date.now() >= nextMarketIntelRunAt) {
            runMarketIntelPipeline();
        }
    }, 60 * 1000);
});

// ── ROUTE: Rewrite Email via AI ───────────────────────────────────────────────
app.post('/api/tracking/:id/ai-edit', async (req: Request, res: Response) => {
    const id = req.params.id;
    const { feedback } = req.body;

    if (!feedback) {
        res.status(400).json({ error: 'Missing feedback' });
        return;
    }

    const payload = { id: parseInt(id as string), feedback };

    try {
        const out = await runPythonCli(UPDATE_EMAIL_CLI, payload, 'AIEdit');
        res.json(out);
    } catch (e) {
        res.status(500).json({ ok: false, error: String(e) });
    }
});

// ── ROUTE: Update Tracking Metadata (any flat field) ──────────────────────────
app.post('/api/tracking/:id/metadata', async (req: Request, res: Response) => {
    const id = req.params.id;
    const { field, value } = req.body;

    if (!field || value === undefined) {
        res.status(400).json({ error: 'Missing field or value' });
        return;
    }

    const payload = { id: parseInt(id as string), field, value };

    try {
        const out = await runPythonCli(UPDATE_METADATA_CLI, payload, 'MetadataUpdate');
        res.json(out);
    } catch (e) {
        res.status(500).json({ ok: false, error: String(e) });
    }
});


// ═══════════════════════════════════════════════════════════════════════════════
//  MARKET INTELLIGENCE ROUTES
// ═══════════════════════════════════════════════════════════════════════════════

const STATS_BASE = path.join(WORKSPACE_ROOT, 'Excel_Generator/Stats_data_collection');
const RISK_JSON = path.join(STATS_BASE, 'risk_factors.json');
const WEATHER_JSON = path.join(STATS_BASE, 'Weather_Forecast', 'weather_strategic_predictions.json');
const UPDATE_ALL = '/Volumes/ssd2/CV Project No 2 copy/Excel_Generator/update_all_stats.py';
const STATS_PY = path.join(STATS_BASE, 'Stats.py');
const WEATHER_PY = path.join(STATS_BASE, 'Weather_LLM_Strategy.py');

// Pipeline states — in-memory, survives until next run
let pipelineState: { status: string; phase: string; startedAt: string | null; log: string[] } = {
    status: 'idle', phase: '', startedAt: null, log: [],
};

let poPipelineState: { status: string; phase: string; startedAt: string | null; log: string[] } = {
    status: 'idle', phase: '', startedAt: null, log: [],
};

// Market Intel System Clock
const INTEL_CLOCK_FILE = path.join(WORKSPACE_ROOT, 'Database/next_intel_run.json');
let nextMarketIntelRunAt = Date.now() + 60 * 60 * 1000;

function loadIntelClock() {
    try {
        if (fs.existsSync(INTEL_CLOCK_FILE)) {
            const raw = JSON.parse(fs.readFileSync(INTEL_CLOCK_FILE, 'utf-8'));
            if (raw.nextRunAt > Date.now()) {
                nextMarketIntelRunAt = raw.nextRunAt;
                console.log(`⏰ [SystemClock] Restored schedule: Next run at ${new Date(nextMarketIntelRunAt).toLocaleTimeString()}`);
            }
        }
    } catch { }
}

function saveIntelClock(time: number) {
    try {
        fs.writeFileSync(INTEL_CLOCK_FILE, JSON.stringify({ nextRunAt: time }));
    } catch { }
}

loadIntelClock();

app.post('/api/market/chat', async (req: Request, res: Response) => {
    const { question } = req.body;
    if (!question) return res.status(400).json({ error: 'Missing question' });
    try {
        const RAG_SCRIPT = path.join(WORKSPACE_ROOT, 'AgenticControl/MarketRAG.py');
        const out = await runPythonCli(RAG_SCRIPT, [question], 'MarketChat');
        res.json({ answer: out });
    } catch (e) {
        res.status(500).json({ error: String(e) });
    }
});

function addPOLog(msg: string) {
    const clean = msg.trim();
    if (clean) {
        console.log(`[PO_LOG] ${clean}`);
        poPipelineState.log.push(clean);
        if (poPipelineState.log.length > 200) poPipelineState.log.shift();
    }
}

// GET /api/stats/risk-factors
app.get('/api/stats/risk-factors', (_req: Request, res: Response) => {
    if (!fs.existsSync(RISK_JSON)) { res.status(404).json({ error: 'risk_factors.json not found' }); return; }
    try { res.json(JSON.parse(fs.readFileSync(RISK_JSON, 'utf-8'))); }
    catch { res.status(500).json({ error: 'Failed to read risk_factors.json' }); }
});

// GET /api/stats/weather-strategy
app.get('/api/stats/weather-strategy', (_req: Request, res: Response) => {
    if (!fs.existsSync(WEATHER_JSON)) { res.status(404).json({ error: 'weather_strategic_predictions.json not found' }); return; }
    try { res.json(JSON.parse(fs.readFileSync(WEATHER_JSON, 'utf-8'))); }
    catch { res.status(500).json({ error: 'Failed to read weather_strategic_predictions.json' }); }
});

// GET /api/stats/pipeline-status
app.get('/api/stats/pipeline-status', (_req: Request, res: Response) => {
    res.json(pipelineState);
});

// GET /api/stats/next-run
app.get('/api/stats/next-run', (_req: Request, res: Response) => {
    res.json({ nextRunAt: nextMarketIntelRunAt });
});

// POST /api/stats/run-pipeline — fires update_all_stats.py, then Stats.py + Weather_LLM_Strategy.py in parallel
app.post('/api/stats/run-pipeline', (_req: Request, res: Response) => {
    if (pipelineState.status === 'running') {
        res.json({ ok: false, message: 'Pipeline already running', state: pipelineState });
        return;
    }

    pipelineState = { status: 'running', phase: 'scrapers', startedAt: new Date().toISOString(), log: [] };
    nextMarketIntelRunAt = Date.now() + 60 * 60 * 1000; // Reset clock on manual trigger
    saveIntelClock(nextMarketIntelRunAt);
    res.json({ ok: true, message: 'Pipeline started', state: pipelineState });

    const addLog = (msg: string) => {
        console.log(`[Pipeline] ${msg}`);
        pipelineState.log.push(`[${new Date().toISOString().slice(11, 19)}] ${msg}`);
        if (pipelineState.log.length > 200) pipelineState.log.shift();
    };

    addLog('Phase 1: Running update_all_stats.py (scrapers)…');

    // ── Phase 1: update_all_stats.py ──────────────────────────────────────────
    const scrapers = spawn(PYTHON_EXE, [UPDATE_ALL], getPythonSpawnOptions());
    scrapers.stdout.on('data', (d: Buffer) => addLog(d.toString().trim()));
    scrapers.stderr.on('data', (d: Buffer) => addLog(`[stderr] ${d.toString().trim()}`));
    scrapers.on('close', (code: number | null) => {
        if (code !== 0) {
            addLog(`update_all_stats.py exited with code ${code} — proceeding anyway`);
        } else {
            addLog('Phase 1 complete. Starting Phase 2 (Stats + Weather in parallel)…');
        }

        pipelineState.phase = 'analysis';

        // ── Phase 2: Stats.py + Weather_LLM_Strategy.py in parallel ──────────
        let done = 0;
        const check = () => { if (++done === 2) { pipelineState.status = 'done'; addLog('✅ All done.'); } };

        addLog('Phase 2: Generating final Market Intelligence reports…');
        const statsProc = spawn(PYTHON_EXE, [STATS_PY], getPythonSpawnOptions());
        statsProc.stdout.on('data', (d: Buffer) => addLog(`[Stats] ${d.toString().trim()}`));
        statsProc.stderr.on('data', (d: Buffer) => addLog(`[Stats|err] ${d.toString().trim()}`));
        statsProc.on('close', (c: number | null) => { addLog(`Stats.py done (code ${c})`); check(); });

        const weatherProc = spawn(PYTHON_EXE, [WEATHER_PY], getPythonSpawnOptions());
        weatherProc.stdout.on('data', (d: Buffer) => addLog(`[Weather] ${d.toString().trim()}`));
        weatherProc.stderr.on('data', (d: Buffer) => addLog(`[Weather|err] ${d.toString().trim()}`));
        weatherProc.on('close', (c: number | null) => { addLog(`Weather_LLM_Strategy.py done (code ${c})`); check(); });
    });
    scrapers.on('error', (err: Error) => { addLog(`Spawn error: ${err.message}`); pipelineState.status = 'error'; });
});

// ── Serve built React frontend — MUST be last so it never shadows API routes ──
// Build first: cd frontend && npm run build
const FRONTEND_DIST = path.resolve(WORKSPACE_ROOT, 'frontend/dist');
if (fs.existsSync(FRONTEND_DIST)) {
    app.use(express.static(FRONTEND_DIST));
    app.get('/{*path}', (req: Request, res: Response) => {
        if (req.path.startsWith('/api/')) {
            res.status(404).json({ error: `API route not found: ${req.path}` });
            return;
        }
        res.sendFile(path.join(FRONTEND_DIST, 'index.html'));
    });
    console.log(`🌐 Serving frontend from: ${FRONTEND_DIST}`);
} else {
    console.log(`⚠️  Frontend not built. Run: cd frontend && npm run build`);
}