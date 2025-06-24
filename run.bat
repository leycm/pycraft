@echo off
REM Install dependencies first
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

REM Start the server
echo "Starting server..."
start "PyCraft Server" cmd /k "python -m server.server"

REM Wait for 2 seconds to ensure server is running
timeout /t 2 /nobreak > nul

REM Start first client
echo "Starting client 1..."
start "PyCraft Client 1" cmd /k "python -m client.client"

REM Wait for 1 second before starting second client
timeout /t 1 /nobreak > nul

REM Start second client
echo "Starting client 2..."
start "PyCraft Client 2" cmd /k "python -m client.client"

echo "All components started."