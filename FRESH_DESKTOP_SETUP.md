# StegaShield: fresh Windows desktop setup

This guide runs the complete StegaShield development system on a new Windows
computer. It assumes the extracted/cloned workspace has this shape:

```text
Mihisara - StegaSheild/
|-- .env.example
|-- requirements.txt
|-- backend/                  Python import compatibility package
`-- stegashield-gateway/
    |-- backend/              FastAPI application
    |-- frontend/             React + Vite portal
    |-- supabase/             Database migrations and tests
    `-- tests/                Backend tests
```

Run backend commands from the **outer workspace folder**, the folder containing
the top-level `requirements.txt`. This is important because FastAPI loads the
top-level `.env` from the current working directory.

## 1. Install the prerequisites

Install:

- Git (only needed when cloning the repository)
- Python 3.12
- Node.js 20 or newer (an LTS release is recommended)
- A modern browser
- A Supabase development project

Optional:

- Docker Desktop, only when running Supabase locally
- VS Code

Restart PowerShell after installing Python or Node.js, then verify:

```powershell
python --version
node --version
npm --version
```

## 2. Obtain the project

Clone it with Git, or securely copy and extract the project archive. Do not copy
`.venv`, `node_modules`, or an old `.env`; those are machine-specific or secret.

Open PowerShell in the outer workspace folder. For example:

```powershell
cd "C:\Projects\Mihisara - StegaSheild"
```

All paths below are relative to that folder.

## 3. Create the Python environment

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`Set-ExecutionPolicy -Scope Process` affects only the current PowerShell window.

## 4. Configure the backend

Create the top-level `.env`:

```powershell
Copy-Item .env.example .env
```

Generate a watermark secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `.env` and replace every placeholder. The file must contain:

```dotenv
APP_ENV=development
PDF_ENABLED=false
APP_NAME=StegaShield Gateway
API_V1_PREFIX=/api/v1
MAX_UPLOAD_SIZE_BYTES=10485760
WATERMARK_SECRET=PASTE_THE_GENERATED_RANDOM_VALUE
ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
SUPABASE_SECRET_KEY=YOUR_SERVER_SECRET_KEY
SUPABASE_JWT_ISSUER=https://YOUR_PROJECT_REF.supabase.co/auth/v1
```

Get the URL and keys from the Supabase project's **Connect** dialog or
**Settings > API Keys**. Use a publishable key for
`SUPABASE_PUBLISHABLE_KEY` and a server secret key for
`SUPABASE_SECRET_KEY`.

Security requirements:

- Never commit or share `.env`.
- Never put `SUPABASE_SECRET_KEY` or `WATERMARK_SECRET` in the frontend.
- Do not use a secret/service-role key as the publishable key.
- Use the same `WATERMARK_SECRET` for files that must remain attributable.
  Changing it makes previously issued watermarks cryptographically unverifiable.

There may be a `stegashield-gateway/.env` in an old copy. Do not rely on it.
The supported startup process uses the top-level `.env` and starts FastAPI from
the outer workspace.

## 5. Prepare the Supabase database

If the hosted development project already has all StegaShield migrations, skip
to step 6.

Install the repository-scoped Supabase CLI:

```powershell
cd .\stegashield-gateway
npm install
npx supabase --version
```

Authenticate and link the hosted development project:

```powershell
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
```

Preview the migrations before applying them:

```powershell
npx supabase db push --dry-run
```

If the preview lists only the expected files under `supabase/migrations`, apply
them:

```powershell
npx supabase db push
```

Do not run `db reset --linked`; it deletes remote data. Do not include seed data
in a production database.

Return to the outer workspace:

```powershell
cd ..
```

## 6. Install the frontend

```powershell
cd .\stegashield-gateway\frontend
npm install
cd ..\..
```

The frontend intentionally has no `.env`. It receives only the safe public
Supabase URL and publishable key from FastAPI at `/api/v1/auth/config`.

## 7. Run the automated checks

From the outer workspace with the Python environment active:

```powershell
python -m pytest stegashield-gateway\tests
```

Then test and build the frontend:

```powershell
cd .\stegashield-gateway\frontend
npm test
npm run build
cd ..\..
```

## 8. Start StegaShield

Use two PowerShell terminals.

### Terminal 1: FastAPI backend

Run from the outer workspace:

```powershell
cd "C:\Projects\Mihisara - StegaSheild"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`, then verify:

- Health: <http://127.0.0.1:8000/health>
- Public auth configuration: <http://127.0.0.1:8000/api/v1/auth/config>
- API documentation: <http://127.0.0.1:8000/docs>

The auth-configuration response may contain a Supabase URL and publishable key.
It must never contain the Supabase server secret or watermark secret.

### Terminal 2: React frontend

```powershell
cd "C:\Projects\Mihisara - StegaSheild\stegashield-gateway\frontend"
npm run dev
```

Open <http://127.0.0.1:5173> and sign in using a user created in Supabase Auth.
Stop either development server with `Ctrl+C` in its terminal.

## 9. Create the first administrator

Create a user under **Supabase Dashboard > Authentication > Users**. The
database trigger creates its `profiles` row with the safe default `user` role.

In the Supabase SQL Editor, inspect the profiles and promote only the intended
administrator:

```sql
select id, display_name, role, created_at
from public.profiles
order by created_at;
```

```sql
update public.profiles
set role = 'admin', updated_at = now()
where id = 'ADMIN_USER_UUID';
```

Replace `ADMIN_USER_UUID` with the correct Auth user UUID. Never add a frontend
feature that lets users promote themselves.

## Common problems

### `Public Supabase configuration is incomplete`

FastAPI either loaded placeholder values or was launched from the wrong folder.
Stop it and start it from the outer workspace containing the configured `.env`.
Confirm this URL returns HTTP 200:

```text
http://127.0.0.1:8000/api/v1/auth/config
```

### `ModuleNotFoundError: No module named 'backend'`

Start Uvicorn from the outer workspace using:

```powershell
python -m uvicorn backend.app.main:app --reload
```

Confirm the outer `backend/__init__.py` compatibility package exists.

### Frontend says it cannot reach the backend

Confirm FastAPI is running on port 8000 and that
<http://127.0.0.1:8000/health> works. Vite proxies `/api` to that port.

### `UNABLE_TO_VERIFY_LEAF_SIGNATURE` or `ECONNRESET`

The npm connection is being interrupted or its TLS certificate is being
intercepted. Try a trusted different network, disable VPN interception, or ask
the network administrator for the correct organization CA certificate. Do not
set npm `strict-ssl` to `false`.

### Port already in use

Find the process using a port:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
```

Stop the old development server with `Ctrl+C` in its original terminal.

### Login fails

Confirm the account exists in Supabase Auth, the migrations were applied, and a
matching row exists in `public.profiles`. Also verify that the Supabase project
in `.env` is the same project where the account was created.

## Daily startup summary

Backend terminal:

```powershell
cd "C:\Projects\Mihisara - StegaSheild"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --reload
```

Frontend terminal:

```powershell
cd "C:\Projects\Mihisara - StegaSheild\stegashield-gateway\frontend"
npm run dev
```

