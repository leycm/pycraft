@echo off
echo "Generating assets..."
python generate_assets.py

echo "Starting client..."
python client/client.py 