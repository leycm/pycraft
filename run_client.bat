@echo off
echo "Generating assets..."
python generate_assets.py

REM Check if arguments are provided
if "%1"=="" (
    echo "Starting client with default name 'Player'..."
    python -m client.client
) else (
    if "%2"=="" (
        echo "Starting client with name '%1'..."
        python -m client.client %1
    ) else (
        echo "Starting client with name '%1' and host '%2'..."
        python -m client.client %1 %2
    )
) 