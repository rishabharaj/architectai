from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Option(BaseModel):
    label: str
    description: str = ""


class Question(BaseModel):
    id: str
    category: str
    question: str
    options: list[Option]
    suggestions: list[str] = Field(default_factory=list)


class QuestionPlan(BaseModel):
    questions: list[Question]


class Answer(BaseModel):
    question_id: str
    category: str
    selection: str


class ArchitectureEntry(BaseModel):
    category: str
    selection: str
    details: dict[str, list[str]] | None = None


class ImplementationStep(BaseModel):
    step: int
    title: str
    description: str


class GuideData(BaseModel):
    projectStructure: list[str] = Field(default_factory=list)
    implementationSteps: list[ImplementationStep] = Field(default_factory=list)
    deploymentSteps: list[str] = Field(default_factory=list)
    envVars: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "New Architecture"
    idea: str
    phase: str = "deciding"
    questions: list[Question] = Field(default_factory=list)
    answers: list[Answer] = Field(default_factory=list)
    architecture: list[ArchitectureEntry] = Field(default_factory=list)
    completed_categories: list[str] = Field(default_factory=list)
    remaining_categories: list[str] = Field(default_factory=list)
    current_index: int = 0
    guide: GuideData | None = None
    createdAt: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)

    @property
    def current_question(self) -> Question | None:
        if self.phase != "deciding" or self.current_index >= len(self.questions):
            return None
        return self.questions[self.current_index]


class NewProject(BaseModel):
    idea: str = Field(min_length=10, max_length=3000)


class SubmitAnswer(BaseModel):
    question_id: str
    selection: str = Field(min_length=1, max_length=200)


class NewCategory(BaseModel):
    category: str = Field(min_length=2, max_length=60)


class RenameProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=3000)


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str
    content: str
    created_at: str = Field(default_factory=now)

