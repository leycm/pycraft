@echo off
REM Install dependencies first
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

REM Start the server
echo "Starting server..."
start "PyCraft Server" cmd /k "python -m server.server"

REM Wait for 2 seconds to ensure server is running
timeout /t 2 /nobreak > nul

REM Start first client with name Steve
echo "Starting client 1 (Steve)..."
start "PyCraft Client 1 - Steve" cmd /k "python -m client.client Steve localhost"

REM Wait for 1 second before starting second client
timeout /t 1 /nobreak > nul

REM Start second client with name Alex
echo "Starting client 2 (Alex)..."
start "PyCraft Client 2 - Alex" cmd /k "python -m client.client Alex localhost"

echo "All components started."
echo "Client 1: Steve"
echo "Client 2: Alex"