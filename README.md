# Finn: AI-Powered Financial Intelligence Agent

Finn is a high-fidelity personal finance assistant designed for modern expense tracking. It combines **Local AI** (via Ollama) with **Cloud OCR** (via Mistral) to provide a privacy-conscious yet powerful financial management experience.

## 🚀 Key Features

- **Hybrid OCR Pipeline**: High-accuracy receipt extraction using Mistral OCR (supports PDFs and Images) paired with local Ollama structuring.
- **Dynamic Budgeting**: Multi-timeline budget goals (Monthly, 6-Month, Yearly) with real-time health scoring and category-specific tracking.
- **Commitment Tracking**: Automated detection of recurring subscriptions and upcoming financial commitments.
- **Universal Search**: Unified keyword search across all transaction history (Ledger).
- **Interactive Analytics**: Premium Dashboard featuring spending trajectory charts, category distribution, and cash flow forecasts.
- **AI Chat Interface**: Narrated financial insights using a LangGraph-powered production agent.

## 🛠️ Technical Architecture

### Backend (FastAPI + SQLAlchemy)
- **Engine**: FastAPI for high-performance asynchronous API endpoints.
- **Database**: SQLite with a multi-model schema (Transactions, Goals, Subscriptions, Chat History).
- **Intelligence**: 
  - **Mistral OCR**: Cloud-based extraction for high-fidelity receipt parsing.
  - **Ollama (Gemma-2-9b)**: Local structuring and reasoning for privacy and speed.
  - **LangGraph**: Orchestrates complex financial tool-calling for the chat agent.

### Frontend (Next.js + Tailwind CSS)
- **Framework**: Next.js 15 (App Router).
- **Styling**: Vanilla-flexible CSS with a premium "Glassmorphism" aesthetic.
- **State Management**: React Hooks + Direct API Integration.
- **Charts**: Recharts for responsive financial visualization.

## 📦 Setup & Installation

### 1. Prerequisites
- **Node.js**: v18.0.0 or higher.
- **Python**: v3.12.0 or higher.
- **Ollama**: Installed and running locally.
- **Mistral API Key**: Required for OCR features.

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
MISTRAL_API_KEY=your_mistral_key_here
OLLAMA_URL=http://localhost:11434
MODEL_NAME=gemma2:9b
UPLOAD_DIR=./uploads
```

### 3. Installation
**Backend Setup:**
```bash
# Recommended: Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

**Frontend Setup:**
```bash
cd frontend
npm install
```

### 4. Running the Application
**Start Backend:**
```bash
python backend/main.py
```

**Start Frontend:**
```bash
cd frontend
npm run dev
```

Visit `http://localhost:3000` to access the Finn dashboard.

## 📂 Project Structure
- `backend/`: FastAPI application, models, and AI pipelines.
- `frontend/src/app/`: Next.js pages and dashboard components.
- `frontend/src/components/`: Shared UI components (ConfirmModal, etc.).
- `uploads/`: Temporary storage for receipt processing.

---
