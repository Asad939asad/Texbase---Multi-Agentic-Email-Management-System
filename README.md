---
title: TEXBase Multi-Agentic System
emoji: 📧
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# TEXBase Multi-Agentic Email Management System

This is a multi-agentic system for managing B2B textile emails, purchase orders, and market intelligence.

## Features
- **Agentic Email Editor**: Iterative email drafting with persona control.
- **PO Quotation Predictor**: Grounded price predictions for textile line items.
- **Market Intelligence RAG**: Real-time analysis of textile commodity trends.
- **Drift Monitoring**: Integrated feedback loops and performance analysis.

## Implementation
The system uses a React frontend and a Flask/Node.js backend. LLM processing is handled via a remote ngrok endpoint to a local Qwen model.
