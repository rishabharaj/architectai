from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ChatMessage, Project


def initialize_firebase(project_id: str, credentials_path: str = "", credentials_json: str = ""):
    import firebase_admin
    from firebase_admin import credentials

    try:
        return firebase_admin.get_app()
    except ValueError:
        options = {"projectId": project_id} if project_id else None
        if credentials_json:
            credential = credentials.Certificate(json.loads(credentials_json))
        elif credentials_path:
            credential = credentials.Certificate(credentials_path)
        else:
            credential = None
        return firebase_admin.initialize_app(credential=credential, options=options)


class SQLiteStore:
    """Persistent local demo store. Firebase mode uses FirestoreStore below."""

    def __init__(self, path: str):
        self.path = str(Path(path).resolve())
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, owner TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner, updated_at)")
            db.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS messages_project ON messages(owner, project_id, created_at)")

    def _connect(self):
        return sqlite3.connect(self.path)

    def save(self, owner: str, project: Project) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?)", (project.id, owner, project.updated_at, project.model_dump_json()))

    def get(self, owner: str, project_id: str) -> Project | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM projects WHERE id=? AND owner=?", (project_id, owner)).fetchone()
        return Project.model_validate_json(row[0]) if row else None

    def list(self, owner: str) -> list[Project]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM projects WHERE owner=? ORDER BY updated_at DESC", (owner,)).fetchall()
        return [Project.model_validate_json(row[0]) for row in rows]

    def delete(self, owner: str, project_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM messages WHERE owner=? AND project_id=?", (owner, project_id))
            db.execute("DELETE FROM projects WHERE owner=? AND id=?", (owner, project_id))

    def add_message(self, owner: str, project_id: str, message: ChatMessage) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?)", (message.id, project_id, owner, message.created_at, message.model_dump_json()))

    def messages(self, owner: str, project_id: str) -> list[ChatMessage]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM messages WHERE owner=? AND project_id=? ORDER BY created_at, rowid", (owner, project_id)).fetchall()
        return [ChatMessage.model_validate_json(row[0]) for row in rows]

    def clear_messages(self, owner: str, project_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM messages WHERE owner=? AND project_id=?", (owner, project_id))


class FirestoreStore:
    """Uses the existing users/{uid}/chats/{id} collection for migration compatibility."""

    def __init__(self, project_id: str, credentials_path: str = "", credentials_json: str = ""):
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.credentials_json = credentials_json
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from firebase_admin import firestore
            initialize_firebase(self.project_id, self.credentials_path, self.credentials_json)
            self._client = firestore.client()
        return self._client

    def _collection(self, owner: str):
        return self.client.collection("users").document(owner).collection("chats")

    def save(self, owner: str, project: Project) -> None:
        self._collection(owner).document(project.id).set(project.model_dump(mode="json"))

    def get(self, owner: str, project_id: str) -> Project | None:
        snapshot = self._collection(owner).document(project_id).get()
        if not snapshot.exists:
            return None
        return Project.model_validate({"id": snapshot.id, **snapshot.to_dict()})

    def list(self, owner: str) -> list[Project]:
        projects = [Project.model_validate({"id": doc.id, **doc.to_dict()}) for doc in self._collection(owner).stream()]
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def delete(self, owner: str, project_id: str) -> None:
        ref = self._collection(owner).document(project_id)
        for message in ref.collection("messages").stream():
            message.reference.delete()
        ref.delete()

    def add_message(self, owner: str, project_id: str, message: ChatMessage) -> None:
        self._collection(owner).document(project_id).collection("messages").document(message.id).set(message.model_dump(mode="json"))

    def messages(self, owner: str, project_id: str) -> list[ChatMessage]:
        docs = self._collection(owner).document(project_id).collection("messages").stream()
        messages = [ChatMessage.model_validate(doc.to_dict()) for doc in docs]
        return sorted(messages, key=lambda m: (m.created_at, m.id))

    def clear_messages(self, owner: str, project_id: str) -> None:
        ref = self._collection(owner).document(project_id).collection("messages")
        for message in ref.stream():
            message.reference.delete()

