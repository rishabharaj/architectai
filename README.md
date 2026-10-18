# Architect AI — Python backend edition

Architect AI turns a startup idea into an architecture questionnaire, saved decisions, an implementation guide, and a contextual chat. React/Vite handles the interface. FastAPI handles APIs, persistence, AI calls, and exports.

```text
React/Vite ── Firebase sign-in token ──> FastAPI ──> Firestore
                                       │
                                       └── LangChain ──> OpenAI GPT-5.4 Mini
```

Local demo mode uses SQLite instead of Firestore and labeled example AI output if no OpenAI key is configured.

## Run locally on Windows

The Desktop copy includes local demo environment files and installed dependencies. Open two PowerShell windows:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173/` for Firebase sign-in. Python API docs are at `http://127.0.0.1:8000/docs`. Old `127.0.0.1:5173` tabs redirect to `localhost` when refreshed.

For a fresh clone, install dependencies first:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\frontend
npm install
```

## Enable OpenAI and Firebase

1. Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`.
2. Put a working OpenAI API key in `OPENAI_API_KEY` in the backend file. `OPENAI_MODEL` defaults to `gpt-5.4-mini`.
3. For real accounts and Firestore, set `APP_MODE=firebase` and `VITE_APP_MODE=firebase`.
4. Fill the `VITE_FIREBASE_*` values from Firebase web app settings. Enable Google and/or email sign-in.
5. Set backend `FIREBASE_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS`. In Firebase Console, open Project settings → Service accounts → Generate new private key, and save the downloaded JSON outside this repository. `GOOGLE_APPLICATION_CREDENTIALS` must be its full file path, for example `C:/Users/HP/Downloads/your-project-firebase-adminsdk.json`. This is a backend-only credential; never put it in `frontend/.env.local` or share it publicly. On Vercel, use `FIREBASE_SERVICE_ACCOUNT_JSON` instead of a file path.
6. Add `localhost` to Firebase Authentication → Settings → Authorized domains if it is missing. Open the frontend at `http://localhost:5173/`.

If OpenAI returns HTTP 429, check the API key project's usage, balance, and rate limits in the OpenAI dashboard.

## Deploy on Vercel

Import this repository into Vercel and select **Services** as the project framework. The root `vercel.json` builds `frontend/` and `backend/` as two services on one domain, with `/api/*` routed to FastAPI. Leave the project root at the repository root. The frontend uses the same domain for API calls in production, so do not set `VITE_API_BASE_URL` unless the API is deployed elsewhere.

Set these environment variables in Vercel before deploying:

| Variable | Value |
| --- | --- |
| `APP_MODE` | `firebase` |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Entire contents of the downloaded Firebase Admin SDK JSON file; store as a sensitive backend secret |
| `OPENAI_API_KEY` | OpenAI API key; backend only |
| `OPENAI_MODEL` | Optional; defaults to `gpt-5.4-mini` |
| `VITE_APP_MODE` | `firebase` |
| `VITE_FIREBASE_API_KEY` | Firebase web app API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase web app auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase web app project ID |
| `VITE_FIREBASE_APP_ID` | Firebase web app ID |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase web app messaging sender ID |

After the first deployment, add its exact hostname (without `https://`) in Firebase Authentication → Settings → Authorized domains. Add a custom domain there too if you use one. The JSON credential and OpenAI key must never be committed or placed in `VITE_*` variables.

Keep the OpenAI key and service-account file server-side. Do not commit `.env` files. The backend verifies Firebase ID tokens and scopes every project to the authenticated UID.

Existing saved blueprints are read from `users/{uid}/chats/{projectId}`. The new format adds saved questions and answers. Existing completed blueprints still open. New chat messages live in `users/{uid}/chats/{projectId}/messages`.

The included `firestore.rules` blocks direct client database access because this frontend uses FastAPI. If the old deployed Next.js site shares the same Firebase project, deploying these rules would stop its direct Firestore reads/writes. Deploy them only when that site has been migrated or uses a separate Firebase project.

## Model-call strategy

- One LangChain/OpenAI call generates and saves the question queue.
- Answer submissions only update saved state; they do not call the model.
- One call generates the guide. Reopening it returns the saved result.
- Each new chat message uses a model call. The backend sends the decisions and up to eight recent messages, then stores the reply.

Demo mode uses a fixed local identity and is intended only for local use. Bind it to `127.0.0.1` as shown. REST handles project actions; server-sent events stream chat replies.

## Test and build

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
```

FastAPI lists every endpoint at `/docs`, including projects, answers, guide, chat, and PDF/Markdown export.
