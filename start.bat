@echo off
REM One-command start (Windows): builds the UI once, then serves everything on http://127.0.0.1:8000
cd /d "%~dp0"
if not exist frontend\dist (
  cd frontend
  call npm install
  call npm run build
  cd ..
)
cd backend
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if not exist .env copy .env.example .env
echo Open http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
