# ── Dockerfile ───────────────────────────────────────────────────────────────
# Multi-stage build for TEXBase Agent API
#
# BASE IMAGE JUSTIFICATION:
#   node:20-slim is chosen because the primary entry point is a Node.js/Express
#   server that orchestrates Python agents via child_process.spawn(). The -slim
#   variant reduces the image footprint from ~1 GB to ~200 MB while retaining
#   the full Node.js runtime.  Python 3 is added as a system package.
#
# LAYER ORDERING STRATEGY:
#   Dependencies are installed BEFORE source code is copied.  This means that
#   a source-code-only change rebuilds only the final COPY layer while all
#   dependency layers are served from Docker's build cache.
#
#   Order: system deps → Python deps → Node deps → source code
#
# WHY NOT MULTI-STAGE?
#   The final image must contain both Node and Python runtimes because the
#   Express server spawns Python scripts at request time.  Splitting them into
#   separate stages would prevent the server from reaching the Python binary.
# ─────────────────────────────────────────────────────────────────────────────

FROM node:20

# ── 1. System dependencies (changes rarely — cached aggressively) ──────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── 2. Python dependencies (changes occasionally) ─────────────────────────
COPY AgenticControl/PO:Quotation/requirements.txt ./requirements.txt
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install PyTorch CPU-only FIRST to prevent pip from downloading ~1.5 GB of
# NVIDIA CUDA libraries (nvidia-cudnn-cu13, nvidia-cublas, etc.) that are
# completely useless in a non-GPU container.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir python-dotenv

# ── 3. Node dependencies (changes occasionally) ───────────────────────────
COPY backend/package*.json ./backend/
RUN cd backend && npm install && npm rebuild sqlite3 --build-from-source

# ── 4. Application source (changes most often — last layer) ───────────────
COPY . .

# ── 5. Runtime environment ────────────────────────────────────────────────
ENV NODE_ENV=production
ENV WORKSPACE_ROOT=/app
ENV PYTHON_EXE=/opt/venv/bin/python3

EXPOSE 8000

# Health-check: the agent-api must respond on /api/health
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fs http://localhost:8000/api/health || exit 1

CMD ["npm", "--prefix", "backend", "run", "dev"]
