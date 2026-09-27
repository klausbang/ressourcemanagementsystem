"""Vercel entry point. Vercel's Python runtime auto-detects a WSGI app named `app` in
this file and wraps it as a serverless function - see vercel.json, which routes every
path to this one function so Flask's own routing (blueprints, static files) handles
everything, rather than Vercel trying to split routes itself.

Nothing else belongs in this file - all real app setup lives in app/__init__.py, same as
local `python run.py`. create_app() picks Postgres vs SQLite from the DATABASE
environment variable alone (see reusable_modules/database), so the only thing that
differs between "python run.py" and this is which environment variables are set - see
README.md "Deploying to Vercel" for exactly which ones Vercel needs.
"""
from app import create_app

app = create_app()
