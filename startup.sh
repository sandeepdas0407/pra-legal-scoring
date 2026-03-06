#!/bin/bash
# Azure App Service startup script
# Initialise the database on first run, then start gunicorn
python -c "from database import init_db; init_db()"
gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=2 app:app
