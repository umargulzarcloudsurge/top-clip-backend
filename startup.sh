#!/bin/bash

# Upgrade pip and ensure setuptools + wheel are available before install
python -m pip install --upgrade pip setuptools wheel

# Now install your app
python -m pip install -r requirements.txt

# Start your app (adjust based on your framework)
gunicorn app:app
