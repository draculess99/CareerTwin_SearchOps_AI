#!/usr/bin/env bash
set -e

# Render sets the public-facing port via the PORT environment variable.
RENDER_PORT="${PORT:-8501}"

echo "Starting Flask Backend on internal port 5050..."
# Temporarily override PORT so the Flask backend binds to 5050 internally
export PORT=5050
export FLASK_DEBUG=0
python backend/app.py &
API_PID=$!

# Ensure the backend process is killed if the container exits
trap 'kill $API_PID' EXIT

# Give the backend a moment to start up
sleep 2

echo "Starting Streamlit Frontend on port ${RENDER_PORT}..."
# Tell Streamlit how to reach the local backend
export API_URL="http://127.0.0.1:5050"

# Start Streamlit in the foreground bound to the Render assigned port
streamlit run frontend/streamlit_app.py --server.port="${RENDER_PORT}" --server.address=0.0.0.0
