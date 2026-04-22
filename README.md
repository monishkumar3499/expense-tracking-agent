# Finn: AI-Powered Expense Tracking Agent

Finn is a sophisticated personal finance assistant built with a hybrid Local/Remote AI architecture. It offers real-time financial intelligence, automated receipt extraction, and deep spending analysis.

## ✨ Features
- **AI OCR**: Extract transaction data from receipts, statements, and screenshots using local models (`moondream`).
- **Natural Language Reasoning**: Chat with your finances using local LLMs (`qwen2.5`).
- **Automated Categorization**: Instant grouping of expenses using smart keyword matching and AI hints.
- **Visual Analytics**: Interactive dashboards with real-time budget tracking and spending trends.
- **Privacy First**: Local AI processing ensures your sensitive financial data stays on your hardware.

## 🛠️ Tech Stack
- **Frontend**: Next.js 16, Tailwind CSS (Claude-inspired Light Theme).
- **Backend**: FastAPI, SQLAlchemy, SQLite.
- **Intelligence**: Ollama (qwen2.5, moondream), Gemini (Fallback).

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.12+
- [Ollama](https://ollama.com/) (Pulled `qwen2.5:1.5b` and `moondream`)

### Setup
1. Clone the repository and navigate to the root.
2. Install dependencies:
   - Backend: `pip install -r backend/requirements.txt`
   - Frontend: `npm install`
3. Configure your `.env` with your Gemini API key (optional fallback).
4. Run the application:
   - Backend: `cd backend && python main.py`
   - Frontend: `npm run dev`

Visit `http://localhost:3000` to start tracking!
