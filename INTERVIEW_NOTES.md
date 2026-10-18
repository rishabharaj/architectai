# Architect AI: interview walkthrough

## 60-second explanation

"Architect AI converts a startup idea into a technical plan. React handles the interface. FastAPI owns the business logic and verifies Firebase sign-in tokens. LangChain sends structured question and guide requests to OpenAI. Firestore stores each project's question queue, answers, blueprint, and chat messages. Generating questions is one model call, answering questions is database-only, and generating the final guide is another model call. Chat uses saved decisions and a bounded recent history."

## Live demo

1. Enter an idea and show the generated questions.
2. Answer two questions and refresh; progress resumes.
3. Finish and generate the guide. Opening it again returns the saved result.
4. Ask about a selected decision and refresh; the conversation returns.
5. Export PDF or Markdown. Open `/docs` to show the Python API.

## Design decisions

- **FastAPI:** typed requests, clear endpoints, automatic API docs.
- **Firestore:** the original project already used Firebase Auth and stored blueprints there, so existing accounts and documents remain usable.
- **LangChain:** prompt templates, OpenAI integration, and structured output. Persistent state lives in Firestore.
- **Question cost:** questions are generated once and saved; answering is database-only.
- **No RAG or WebSocket:** this app does not search a document corpus, and simpler server-sent events stream chat. Neither removes model calls for new AI replies.
- **Security:** FastAPI verifies the Firebase ID token and uses its UID to access that user's documents. AI credentials stay server-side.
- **Chat cost:** send saved decisions and only the most recent eight messages.

The local demo uses SQLite and labeled example AI output until OpenAI and Firebase credentials are configured. Real AI and cloud persistence require those credentials; they are not in source control.
