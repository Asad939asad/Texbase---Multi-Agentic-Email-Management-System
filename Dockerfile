# ── Dockerfile ───────────────────────────────────────────────────────────────
# Fast build: Uses the pre-baked 'texbase-libs' image

FROM texbase-libs

WORKDIR /app

# The libraries are already in /opt/venv and backend/node_modules from the base image.
# We just copy the latest source code.
COPY . .

# Ensure the environment is correct
ENV NODE_ENV=production
ENV WORKSPACE_ROOT=/app
ENV PYTHON_EXE=/opt/venv/bin/python3

EXPOSE 8000

# Health-check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fs http://localhost:8000/api/health || exit 1

CMD ["npm", "--prefix", "backend", "run", "dev"]
