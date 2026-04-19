# Job Application Tracking System (Django + Tailwind)

## Features
- Authentication (register/login/logout)
- Job application CRUD with status/category/cv tracking
- Dynamic per-user categories with default `Uncategorized`
- CV manager with versioning and optional cover letter
- Interview rounds + interview questions tracker
- Notes and activity timeline
- Follow-up reminders on dashboard
- Search + combined filters + pagination
- Responsive Tailwind templates and kanban board view

## Project Structure
- `accounts` - registration/login
- `jobs` - jobs, categories, CVs, notes, reminders, activity timeline
- `interviews` - interview rounds/questions
- `dashboard` - analytics home

## Setup
1. Create virtual environment and install dependencies:
   - `python -m venv .venv`
   - `.venv\\Scripts\\python.exe -m pip install -r requirements.txt`
2. Run migrations:
   - `.venv\\Scripts\\python.exe manage.py makemigrations`
   - `.venv\\Scripts\\python.exe manage.py migrate`
3. Create superuser:
   - `.venv\\Scripts\\python.exe manage.py createsuperuser`
4. Run server:
   - `.venv\\Scripts\\python.exe manage.py runserver`

## PostgreSQL in Production
Set environment variables:
- `DATABASE_URL` (recommended for Render)
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=False`

## Render Deploy (Secure + PostgreSQL)
This repository includes:
- `render.yaml` for one-click Render Blueprint deployment
- `Procfile` for process start command
- `runtime.txt` to pin Python version

### Option A: Blueprint Deploy (Recommended)
1. Push this project to GitHub.
2. In Render, choose **New + > Blueprint** and select your repo.
3. Render will create:
   - Web service (`jobtracker`)
   - PostgreSQL database (`jobtracker-db`)
4. After deploy, run `python manage.py createsuperuser` from Render Shell.

### Option B: Manual Web Service
1. Create a PostgreSQL database in Render.
2. Create a Web Service and set:
   - Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start command: `python manage.py migrate --noinput && gunicorn config.wsgi:application --log-file -`
3. Add environment variables:
   - `DJANGO_DEBUG=False`
   - `DJANGO_SECRET_KEY` (strong random value)
   - `DATABASE_URL` (from Render PostgreSQL connection string)
   - `DJANGO_ALLOWED_HOSTS` (e.g. `your-service-name.onrender.com`)
   - `DJANGO_CSRF_TRUSTED_ORIGINS` (e.g. `https://your-service-name.onrender.com`)

### Option C: Existing Render PostgreSQL (Fastest)
If you already have a database URL, use this directly:
1. Keep `render.yaml` as-is and deploy from GitHub with **Blueprint**.
2. In the new web service, open **Environment** and set:
   - `DATABASE_URL` = your existing internal URL
   - Example: `postgresql://<user>:<password>@<host>/<db_name>`
3. Redeploy the service.
4. Open **Shell** and run:
   - `python manage.py createsuperuser`

### Security Defaults Enabled in Production (`DJANGO_DEBUG=False`)
- HTTPS redirect via proxy header
- Secure session and CSRF cookies
- HSTS headers
- Referrer and frame protections
- WhiteNoise compressed static files

## Sample Data
Run:
- `.venv\\Scripts\\python.exe manage.py seed_sample_data --username demo --password demo12345`

Then log in with those credentials.

## Google Login Setup
1. Go to Google Cloud Console and create an OAuth Client ID (Web application).
2. Add this authorized redirect URI:
   - `http://127.0.0.1:8000/accounts/google/login/callback/`
3. Set these environment variables before running the app:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
4. If you prefer admin-based setup, you can still create a `SocialApp` in Django admin and attach it to Site ID 1.
5. Save and open login page to use “Continue with Google”.
