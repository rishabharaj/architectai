import asyncio

from fastapi.testclient import TestClient
from langchain_core.exceptions import ModelRateLimitError

from app.ai import ArchitectAI
from app.config import Settings
from app.main import create_app
from app.models import GuideData, ImplementationStep, Option, Question, QuestionPlan
from app.storage import SQLiteStore, initialize_firebase


class FakeAI:
    def __init__(self):
        self.question_calls = 0
        self.guide_calls = 0

    async def generate_questions(self, idea):
        self.question_calls += 1
        return [
            Question(id="q1", category="Frontend", question="Which UI?", options=[Option(label="React"), Option(label="Vue")]),
            Question(id="q2", category="Database", question="Which database?", options=[Option(label="Firestore"), Option(label="PostgreSQL")]),
        ]

    async def generate_guide(self, project):
        self.guide_calls += 1
        return GuideData(
            projectStructure=["frontend/", "backend/"],
            implementationSteps=[ImplementationStep(step=1, title="Build", description="Implement the selected stack")],
            deploymentSteps=["Deploy"], envVars=["OPENAI_API_KEY"],
        )

    async def chat(self, project, history, message):
        yield "Use "
        yield project.architecture[0].selection


def client(tmp_path, ai=None):
    settings = Settings(app_mode="demo", sqlite_path=str(tmp_path / "test.sqlite3"))
    return TestClient(create_app(settings, ai=ai or FakeAI()))


def test_questions_are_generated_once_and_progress_survives_restart(tmp_path):
    ai = FakeAI()
    first = client(tmp_path, ai)
    created = first.post("/api/projects", json={"idea": "A local food delivery app"})
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert ai.question_calls == 1
    answered = first.post(f"/api/projects/{project_id}/answers", json={"question_id": "q1", "selection": "React"})
    assert answered.status_code == 200
    assert answered.json()["current_index"] == 1
    assert ai.question_calls == 1

    restarted = client(tmp_path, ai)
    loaded = restarted.get(f"/api/projects/{project_id}").json()
    assert loaded["answers"][0]["selection"] == "React"
    assert loaded["current_index"] == 1
    assert restarted.post(f"/api/projects/{project_id}/answers", json={"question_id": "q1", "selection": "React"}).status_code == 409
    complete = restarted.post(f"/api/projects/{project_id}/answers", json={"question_id": "q2", "selection": "Firestore"}).json()
    assert complete["phase"] == "complete"
    assert ai.question_calls == 1


def test_guide_chat_exports_and_clear(tmp_path):
    ai = FakeAI()
    api = client(tmp_path, ai)
    project_id = api.post("/api/projects", json={"idea": "A local food delivery app"}).json()["id"]
    for question_id, selection in [("q1", "React"), ("q2", "Firestore")]:
        assert api.post(f"/api/projects/{project_id}/answers", json={"question_id": question_id, "selection": selection}).status_code == 200
    assert api.post(f"/api/projects/{project_id}/guide").status_code == 200
    assert api.post(f"/api/projects/{project_id}/guide").status_code == 200
    assert ai.guide_calls == 1
    streamed = api.post(f"/api/projects/{project_id}/chat", json={"message": "What UI?"})
    assert "Use " in streamed.text
    assert "React" in streamed.text
    messages = api.get(f"/api/projects/{project_id}/messages").json()
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert api.get(f"/api/projects/{project_id}/export?format=md").text.startswith("# Architect AI Blueprint")
    assert api.get(f"/api/projects/{project_id}/export?format=pdf").content.startswith(b"%PDF")
    assert api.delete(f"/api/projects/{project_id}/messages").status_code == 204
    assert api.get(f"/api/projects/{project_id}/messages").json() == []


def test_firestore_mode_requires_login(tmp_path):
    settings = Settings(app_mode="firebase")
    api = TestClient(create_app(settings, store=SQLiteStore(str(tmp_path / "store.sqlite3")), ai=FakeAI()))
    assert api.get("/api/projects").status_code == 401
    assert api.post("/api/projects", json={"idea": "A local food delivery app"}).status_code == 401


def test_storage_is_scoped_to_owner(tmp_path):
    store = SQLiteStore(str(tmp_path / "store.sqlite3"))
    api = TestClient(create_app(Settings(app_mode="demo"), store=store, ai=FakeAI()))
    project_id = api.post("/api/projects", json={"idea": "A local food delivery app"}).json()["id"]
    assert store.get("different-user", project_id) is None
    assert store.list("different-user") == []


def test_firebase_credentials_path_from_env_is_passed_to_admin(tmp_path, monkeypatch):
    import firebase_admin
    from firebase_admin import credentials

    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_APPLICATION_CREDENTIALS=C:/private/firebase-admin.json\n")
    settings = Settings(_env_file=env_file)
    seen = {}

    def no_existing_app():
        raise ValueError("No Firebase app")

    def certificate(path):
        seen["path"] = path
        return "credential"

    def initialize_app(credential=None, options=None):
        seen["credential"] = credential
        seen["options"] = options
        return "app"

    monkeypatch.setattr(firebase_admin, "get_app", no_existing_app)
    monkeypatch.setattr(credentials, "Certificate", certificate)
    monkeypatch.setattr(firebase_admin, "initialize_app", initialize_app)

    assert initialize_firebase("my-project", settings.google_application_credentials) == "app"
    assert seen == {"path": "C:/private/firebase-admin.json", "credential": "credential", "options": {"projectId": "my-project"}}


def test_ai_rate_limit_has_actionable_response(tmp_path):
    class RateLimitedAI(FakeAI):
        async def generate_questions(self, idea):
            raise ModelRateLimitError("quota exceeded")

    api = client(tmp_path, RateLimitedAI())
    response = api.post("/api/projects", json={"idea": "A local food delivery app"})
    assert response.status_code == 429
    assert "OpenAI" in response.json()["detail"]


def test_openai_model_accepts_question_and_guide_schemas_without_network():
    settings = Settings(app_mode="demo", openai_api_key="sk-test-placeholder", _env_file=None)
    model = ArchitectAI(settings).model
    assert model.model_name == "gpt-5.4-mini"
    model.with_structured_output(QuestionPlan, method="json_schema")
    model.with_structured_output(GuideData, method="json_schema")


def test_demo_questions_work_without_openai_key():
    ai = ArchitectAI(Settings(app_mode="demo", openai_api_key="", _env_file=None))
    questions = asyncio.run(ai.generate_questions("A local food delivery app"))
    assert len(questions) == 6
