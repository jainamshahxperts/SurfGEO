
echo "✅ Installing Chromium for Playwright..."
playwright install chromium

echo "🚀 Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 10000