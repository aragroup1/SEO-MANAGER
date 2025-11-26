# backend/start.sh
#!/bin/bash
echo "Starting SEO Intelligence Platform..."
echo "Current directory: $(pwd)"
echo "Contents of /app: $(ls -la /app)"
echo "Contents of /app/backend: $(ls -la /app/backend)"
echo "Python version: $(python --version)"
echo "Activating virtual environment..."
source /opt/venv/bin/activate
echo "Virtual environment activated"
echo "Python path: $(which python)"
echo "Starting main.py..."
cd /app/backend
python main.py
