# InsightX AI — Full Stack Integration Guide

```
Frontend (React/JSX)  ──→  FastAPI Backend  ──→  NVIDIA NIM / Anthropic
     :3000 / :5173              :8000
```

---

## 📁 Project Structure

```
your-project/
├── backend/
│   ├── main.py          ← FastAPI server  (this file)
│   └── .env             ← API keys
└── frontend/
    └── InsightX_AI.jsx  ← React frontend  (this file)
```

---

## ⚙️ Backend Setup

### 1. Install dependencies
```bash
pip install fastapi uvicorn openai pandas python-dotenv
```

### 2. Create backend/.env
```
AI_PROVIDER=nvidia
AI_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx

# OR for Anthropic:
# AI_PROVIDER=anthropic
# AI_MODEL=claude-opus-4-6
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

### 3. Start the server
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Visit http://localhost:8000/docs for the auto-generated API docs.

---

## 🖥️ Frontend Setup

### If using Vite / Create React App
Just drop `InsightX_AI.jsx` into your `src/` folder and import it.

The API base URL is set at the top of the file:
```js
const API_BASE = "http://localhost:8000";
```
Change this when deploying to production.

---

## 🔌 API Endpoints

| Method | Endpoint | What it does |
|--------|----------|-------------|
| `GET`  | `/api/health` | Check backend status, current model |
| `POST` | `/api/chat` | Send a message, get AI reply |
| `GET`  | `/api/overview` | Get executive overview (on page load) |
| `POST` | `/api/upload-csv` | Upload a new CSV dataset |
| `GET`  | `/api/session/{id}` | Get conversation history |
| `DELETE` | `/api/session/{id}` | Clear conversation (New Chat) |

### POST /api/chat — Request
```json
{
  "message": "Which state has the highest fraud rate?",
  "session_id": "abc123"   // null for first message
}
```

### POST /api/chat — Response
```json
{
  "reply": "Karnataka has the highest fraud rate at 0.232%...",
  "session_id": "abc123",
  "chart_type": "state"    // tells frontend which chart to render
}
```

---

## 🔄 How Sessions Work

1. First message: send `session_id: null` → backend returns a new `session_id`
2. Store that `session_id` in React state
3. Pass it with every subsequent message
4. Backend keeps full conversation history server-side
5. Click "New Chat" → calls `DELETE /api/session/{id}` → clears history

---

## 📂 CSV Upload

Click **"Upload CSV"** in the header to swap the dataset live.
The backend re-profiles the new CSV and updates the AI's context automatically.
All subsequent questions will be answered based on the new data.

---

## 🚀 Deployment

### Backend (e.g. Railway, Render, EC2)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
Update `API_BASE` in InsightX_AI.jsx to your deployed backend URL:
```js
const API_BASE = "https://your-backend.railway.app";
```
Then add your production URL to `allow_origins` in `main.py`.
