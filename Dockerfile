# Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Final Stage
FROM python:3.11-slim
WORKDIR /app

# Install Node.js and system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    curl \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Backend dependencies
COPY backend/package*.json ./backend/
RUN cd backend && npm install

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# Copy source code
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set environment variables
ENV NODE_ENV=production
ENV PORT=7860
ENV WORKSPACE_ROOT=/app
ENV PYTHON_EXE=python3
ENV PYTHONUNBUFFERED=1

# Create necessary directories and set permissions
RUN mkdir -p Database/EmailsUnderReview Database/EmailsSent Database/FollowUps Database/Inbox \
    && chmod -R 777 Database \
    && chmod -R 777 .

# Expose port (Hugging Face expects 7860)
EXPOSE 7860

# Start application
CMD ["npm", "--prefix", "backend", "run", "start"]
