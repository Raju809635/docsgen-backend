# docsgen-backend (Render)

FastAPI backend for the AI Documentation Generator.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

## Deploy to Render

- This repo includes `render.yaml` for Render Blueprint deploy.
- Set environment variables:
  - `OPENAI_API_KEY`
  - `FRONTEND_ORIGIN` (your Vercel URL, e.g. `https://your-app.vercel.app`)

