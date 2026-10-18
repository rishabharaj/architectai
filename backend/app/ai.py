import json
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from .config import Settings
from .models import Answer, ChatMessage, GuideData, ImplementationStep, Option, Project, Question, QuestionPlan


class AIUnavailable(Exception):
    pass


class ArchitectAI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    @property
    def model(self):
        if not self.settings.openai_api_key:
            raise AIUnavailable("OPENAI_API_KEY is missing. Add it to backend/.env to enable AI generation.")
        if self._model is None:
            from langchain_openai import ChatOpenAI

            self._model = ChatOpenAI(
                model=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                max_retries=2,
                timeout=45,
            )
        return self._model

    async def generate_questions(self, idea: str) -> list[Question]:
        if not self.settings.openai_api_key and self.settings.demo:
            return demo_questions()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a practical software architect. Produce exactly 5 to 7 concise multiple-choice architecture questions personalized to the startup idea. Include Platform, Frontend, Backend, Database, Authentication, and Deployment when relevant. Each question must have 2 to 4 sensible options, with a one-sentence tradeoff in each description. Keep categories unique. Do not ask for facts already clear from the idea. Return the required structured schema. Do not invent prices or claim specific services are free."),
            ("human", "Startup idea: {idea}"),
        ])
        result: QuestionPlan = await (prompt | self.model.with_structured_output(QuestionPlan, method="json_schema")).ainvoke({"idea": idea})
        questions: list[Question] = []
        seen: set[str] = set()
        for raw in result.questions:
            category = raw.category.strip()
            if not category or category.lower() in seen or len(raw.options) < 2:
                continue
            seen.add(category.lower())
            questions.append(Question(
                id=f"q{len(questions) + 1}",
                category=category,
                question=raw.question.strip(),
                options=[Option(label=o.label.strip(), description=o.description.strip()) for o in raw.options[:4]],
                suggestions=[],
            ))
        if len(questions) < 3:
            raise AIUnavailable("AI did not return enough valid questions. Please try again.")
        return questions[:7]

    async def generate_guide(self, project: Project) -> GuideData:
        if not self.settings.openai_api_key and self.settings.demo:
            return demo_guide(project.answers)
        decisions = [{"category": a.category, "selection": a.selection} for a in project.answers]
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior software architect. Create an actionable implementation guide for the idea and decisions. Respect user selections. Include a realistic project folder structure, 6 to 10 implementation steps, deployment steps, and environment variable NAMES only. Be concise and avoid invented credentials or prices. Return the required structured schema."),
            ("human", "Idea: {idea}\nDecisions: {decisions}"),
        ])
        result: GuideData = await (prompt | self.model.with_structured_output(GuideData, method="json_schema")).ainvoke({
            "idea": project.idea,
            "decisions": json.dumps(decisions, ensure_ascii=False),
        })
        return result

    async def chat(self, project: Project, history: list[ChatMessage], message: str) -> AsyncIterator[str]:
        if not self.settings.openai_api_key and self.settings.demo:
            answer = f"Demo response: for your idea '{project.idea[:80]}', review the saved decisions and implementation guide. Add OPENAI_API_KEY in backend/.env for a personalized AI answer."
            for word in answer.split(" "):
                yield word + " "
            return
        decisions = ", ".join(f"{a.category}: {a.selection}" for a in project.answers)
        guide_summary = "; ".join(step.title for step in (project.guide.implementationSteps[:6] if project.guide else []))
        system = (
            "You are Architect AI, a practical software architecture assistant. Answer using the saved project context. "
            "Be specific, concise, and explain tradeoffs. If the user changes a decision, explain the impact; do not claim the saved blueprint has changed. "
            f"Idea: {project.idea[:3000]}\nDecisions: {decisions[:2500]}\nGuide steps: {guide_summary[:1000]}"
        )
        messages = [SystemMessage(content=system)]
        for item in history[-8:]:
            if item.role == "user":
                messages.append(HumanMessage(content=item.content[:2000]))
            elif item.role == "assistant":
                messages.append(AIMessage(content=item.content[:2000]))
        messages.append(HumanMessage(content=message))
        async for chunk in self.model.astream(messages):
            content = chunk.content
            if isinstance(content, str) and content:
                yield content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        yield str(block.get("text", ""))


def demo_questions() -> list[Question]:
    raw = [
        ("Platform", "Where will people use this product first?", [("Web app", "Works in a browser and is fastest to validate."), ("Mobile app", "Best for phone-first usage and device features.")]),
        ("Frontend", "Which frontend approach fits your first release?", [("React + Vite", "Simple single-page application."), ("Next.js", "Useful when server rendering and search visibility matter.")]),
        ("Backend", "How should your API be built?", [("FastAPI", "Python API with typed requests and automatic docs."), ("Django", "Python framework with more built-in features.")]),
        ("Database", "Where should project data live?", [("Firestore", "Managed document storage with Firebase integration."), ("PostgreSQL", "Relational storage for structured queries and constraints.")]),
        ("Authentication", "How should users sign in?", [("Firebase Auth", "Managed Google and email sign-in."), ("Email only", "A simpler login experience with more backend ownership.")]),
        ("Deployment", "How will you deploy the first version?", [("Managed hosting", "Lower operational work for a small team."), ("Docker on a VM", "More infrastructure control and maintenance.")]),
    ]
    return [Question(id=f"q{i}", category=category, question=question, options=[Option(label=label, description=description) for label, description in options]) for i, (category, question, options) in enumerate(raw, 1)]


def demo_guide(answers: list[Answer]) -> GuideData:
    selected = {a.category: a.selection for a in answers}
    frontend = selected.get("Frontend", "React + Vite")
    backend = selected.get("Backend", "FastAPI")
    database = selected.get("Database", "Firestore")
    return GuideData(
        projectStructure=["frontend/ — UI and API client", "backend/app/ — API, AI service, and storage", "backend/tests/ — behavior tests"],
        implementationSteps=[
            ImplementationStep(step=1, title="Define user journeys", description="Write down the core actions and data that must persist."),
            ImplementationStep(step=2, title="Build the frontend", description=f"Create the first screens using {frontend}."),
            ImplementationStep(step=3, title="Create the API", description=f"Add validated endpoints in {backend}."),
            ImplementationStep(step=4, title="Persist data", description=f"Store user projects and chat history in {database}."),
            ImplementationStep(step=5, title="Add authentication", description="Verify user identity before every project request."),
            ImplementationStep(step=6, title="Test and deploy", description="Test the main flow, then deploy the UI and API."),
        ],
        deploymentSteps=["Configure environment variables", "Deploy backend", "Deploy frontend", "Run an end-to-end smoke test"],
        envVars=["OPENAI_API_KEY", "FIREBASE_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS"],
    )
