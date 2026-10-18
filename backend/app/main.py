import io
import json
from html import escape

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from langchain_core.exceptions import ModelRateLimitError
from openai import AuthenticationError, RateLimitError

from .ai import AIUnavailable, ArchitectAI
from .config import Settings
from .models import (
    Answer, ArchitectureEntry, ChatInput, ChatMessage, NewCategory, NewProject,
    Option, Project, Question, RenameProject, SubmitAnswer, now,
)
from .storage import FirestoreStore, SQLiteStore, initialize_firebase


AI_RATE_LIMIT_MESSAGE = "OpenAI request limit reached. Check API usage and limits in your OpenAI project."
AI_AUTH_MESSAGE = "OpenAI API key was rejected. Check OPENAI_API_KEY in backend/.env."


def create_app(settings: Settings | None = None, store=None, ai=None) -> FastAPI:
    settings = settings or Settings()
    if settings.app_mode not in {"demo", "firebase"}:
        raise ValueError("APP_MODE must be demo or firebase")
    app = FastAPI(title="Architect AI Python API", version="2.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.state.settings = settings
    app.state.store = store or (SQLiteStore(settings.sqlite_path) if settings.demo else FirestoreStore(settings.firebase_project_id, settings.google_application_credentials, settings.firebase_service_account_json))
    app.state.ai = ai or ArchitectAI(settings)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": settings.app_mode, "ai_configured": bool(settings.openai_api_key)}

    async def owner(authorization: str | None = Header(default=None)) -> str:
        if settings.demo:
            return "demo-local"
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Sign in is required")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            from firebase_admin import auth
            initialize_firebase(settings.firebase_project_id, settings.google_application_credentials, settings.firebase_service_account_json)
            decoded = auth.verify_id_token(token, check_revoked=True, clock_skew_seconds=10)
            return decoded["uid"]
        except Exception as exc:
            raise HTTPException(401, "Invalid or expired sign-in") from exc

    def get_project(uid: str, project_id: str) -> Project:
        try:
            project = app.state.store.get(uid, project_id)
        except Exception as exc:
            raise HTTPException(503, "Database is unavailable; check Firebase credentials") from exc
        if not project:
            raise HTTPException(404, "Project not found")
        if not project.questions and project.architecture:
            project.phase = "complete"  # existing repository documents did not store question queues
        return project

    def save_project(uid: str, project: Project) -> Project:
        project.updated_at = now()
        try:
            app.state.store.save(uid, project)
        except Exception as exc:
            raise HTTPException(503, "Could not save project") from exc
        return project

    @app.get("/api/projects")
    def list_projects(uid: str = Depends(owner)):
        try:
            return app.state.store.list(uid)
        except Exception as exc:
            raise HTTPException(503, "Database is unavailable; check Firebase credentials") from exc

    @app.post("/api/projects", status_code=201)
    async def new_project(body: NewProject, uid: str = Depends(owner)):
        try:
            questions = await app.state.ai.generate_questions(body.idea.strip())
        except (ModelRateLimitError, RateLimitError) as exc:
            raise HTTPException(429, AI_RATE_LIMIT_MESSAGE) from exc
        except AuthenticationError as exc:
            raise HTTPException(503, AI_AUTH_MESSAGE) from exc
        except AIUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, "AI question generation failed. Please retry.") from exc
        project = Project(
            name=body.idea.strip()[:80], idea=body.idea.strip(), questions=questions,
            remaining_categories=[q.category for q in questions],
        )
        return save_project(uid, project)

    @app.get("/api/projects/{project_id}")
    def read_project(project_id: str, uid: str = Depends(owner)):
        return get_project(uid, project_id)

    @app.patch("/api/projects/{project_id}")
    def rename_project(project_id: str, body: RenameProject, uid: str = Depends(owner)):
        project = get_project(uid, project_id)
        project.name = body.name.strip()
        return save_project(uid, project)

    @app.delete("/api/projects/{project_id}", status_code=204)
    def delete_project(project_id: str, uid: str = Depends(owner)):
        get_project(uid, project_id)
        app.state.store.delete(uid, project_id)
        return Response(status_code=204)

    @app.post("/api/projects/{project_id}/answers")
    def submit_answer(project_id: str, body: SubmitAnswer, uid: str = Depends(owner)):
        project = get_project(uid, project_id)
        if project.phase != "deciding" or not project.current_question:
            raise HTTPException(409, "No active question")
        question = project.current_question
        if body.question_id != question.id:
            raise HTTPException(409, "Question is no longer current; reload the project")
        selection = body.selection.strip()
        project.answers.append(Answer(question_id=question.id, category=question.category, selection=selection))
        project.architecture.append(ArchitectureEntry(category=question.category, selection=selection))
        project.completed_categories.append(question.category)
        project.remaining_categories = [cat for cat in project.remaining_categories if cat != question.category]
        project.current_index += 1
        if project.current_index >= len(project.questions):
            project.phase = "complete"
        return save_project(uid, project)

    @app.post("/api/projects/{project_id}/categories")
    def add_category(project_id: str, body: NewCategory, uid: str = Depends(owner)):
        project = get_project(uid, project_id)
        category = body.category.strip()
        if category.lower() in {q.category.lower() for q in project.questions}:
            return project
        if project.guide:
            raise HTTPException(409, "Add categories before generating the guide")
        question = Question(
            id=f"q{len(project.questions) + 1}", category=category,
            question=f"What approach should this project use for {category}?",
            options=[Option(label="Managed service", description="Less setup and maintenance."), Option(label="Custom implementation", description="More control and development work.")],
        )
        project.questions.append(question)
        project.remaining_categories.append(category)
        project.phase = "deciding"
        return save_project(uid, project)

    @app.post("/api/projects/{project_id}/guide")
    async def generate_guide(project_id: str, uid: str = Depends(owner)):
        project = get_project(uid, project_id)
        if project.guide:
            return project
        if project.phase != "complete" or not project.architecture:
            raise HTTPException(409, "Answer all questions first")
        try:
            project.guide = await app.state.ai.generate_guide(project)
        except (ModelRateLimitError, RateLimitError) as exc:
            raise HTTPException(429, AI_RATE_LIMIT_MESSAGE) from exc
        except AuthenticationError as exc:
            raise HTTPException(503, AI_AUTH_MESSAGE) from exc
        except AIUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, "AI guide generation failed. Please retry.") from exc
        return save_project(uid, project)

    @app.get("/api/projects/{project_id}/messages")
    def get_messages(project_id: str, uid: str = Depends(owner)):
        get_project(uid, project_id)
        return app.state.store.messages(uid, project_id)

    @app.delete("/api/projects/{project_id}/messages", status_code=204)
    def clear_messages(project_id: str, uid: str = Depends(owner)):
        get_project(uid, project_id)
        app.state.store.clear_messages(uid, project_id)
        return Response(status_code=204)

    @app.post("/api/projects/{project_id}/chat")
    async def chat(project_id: str, body: ChatInput, uid: str = Depends(owner)):
        if not settings.openai_api_key and not settings.demo:
            raise HTTPException(503, "OPENAI_API_KEY is missing. Add it to backend/.env to enable AI chat.")
        project = get_project(uid, project_id)
        history = app.state.store.messages(uid, project_id)
        message = body.message.strip()
        app.state.store.add_message(uid, project_id, ChatMessage(role="user", content=message))

        async def events():
            answer = ""
            try:
                async for delta in app.state.ai.chat(project, history, message):
                    answer += delta
                    yield f"data: {json.dumps({'type': 'delta', 'text': delta})}\n\n"
                if answer.strip():
                    app.state.store.add_message(uid, project_id, ChatMessage(role="assistant", content=answer.strip()))
                yield 'data: {"type":"done"}\n\n'
            except (ModelRateLimitError, RateLimitError):
                yield f"data: {json.dumps({'type': 'error', 'message': AI_RATE_LIMIT_MESSAGE})}\n\n"
            except AuthenticationError:
                yield f"data: {json.dumps({'type': 'error', 'message': AI_AUTH_MESSAGE})}\n\n"
            except Exception:
                yield 'data: {"type":"error","message":"AI chat failed. Please retry."}\n\n'

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/projects/{project_id}/export")
    def export_project(project_id: str, format: str = "md", uid: str = Depends(owner)):
        project = get_project(uid, project_id)
        markdown = project_markdown(project)
        if format == "md":
            return Response(markdown, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="architect-{project.id[:8]}.md"'})
        if format == "pdf":
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

            output = io.BytesIO()
            document = SimpleDocTemplate(output, title="Architect AI Blueprint")
            styles = getSampleStyleSheet()
            story = []
            for line in markdown.splitlines():
                if not line.strip():
                    story.append(Spacer(1, 8))
                elif line.startswith("# "):
                    story.append(Paragraph(escape(line[2:]), styles["Title"]))
                elif line.startswith("## "):
                    story.append(Paragraph(escape(line[3:]), styles["Heading2"]))
                else:
                    story.append(Paragraph(escape(line.removeprefix("- ")), styles["BodyText"]))
            document.build(story)
            return Response(output.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="architect-{project.id[:8]}.pdf"'})
        raise HTTPException(400, "format must be md or pdf")

    return app


def project_markdown(project: Project) -> str:
    lines = ["# Architect AI Blueprint", "", "## Idea", project.idea, "", "## Architecture Decisions"]
    lines.extend(f"- {entry.category}: {entry.selection}" for entry in project.architecture)
    if project.guide:
        lines.extend(["", "## Project Structure"])
        lines.extend(f"- {item}" for item in project.guide.projectStructure)
        lines.extend(["", "## Implementation Steps"])
        lines.extend(f"- {step.step}. {step.title}: {step.description}" for step in project.guide.implementationSteps)
        lines.extend(["", "## Deployment Steps"])
        lines.extend(f"- {step}" for step in project.guide.deploymentSteps)
        lines.extend(["", "## Environment Variables"])
        lines.extend(f"- {item}" for item in project.guide.envVars)
    return "\n".join(lines) + "\n"


app = create_app()
