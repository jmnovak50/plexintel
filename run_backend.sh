#!/bin/bash

# Activate your virtualenv (if you have one)
source plexenv/bin/activate

# Run the FastAPI backend on port 8489
uvicorn api.main:app --host 0.0.0.0 --port 8489 --reload
