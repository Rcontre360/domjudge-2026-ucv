#!/bin/bash

echo "Starting DOMjudge stack..."
docker compose up -d

echo "Running Python setup script inside the container..."
# We pipe the local setup.py into the container's python3 interpreter
docker exec -i domjudge-domserver python3 < setup.py
