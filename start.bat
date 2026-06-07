@echo off
echo Starting Neo4j...
docker compose up -d
echo.
echo Neo4j may take ~15 seconds to be ready on first launch.
echo Web UI: http://localhost:8000
echo Press Ctrl+C to stop the web server.
echo.
py -m uvicorn server:app --reload
