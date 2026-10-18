from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_mode: str = "firebase"  # firebase or demo
    sqlite_path: str = "./architect_demo.sqlite3"
    firebase_project_id: str = ""
    google_application_credentials: str = ""
    firebase_service_account_json: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def demo(self) -> bool:
        return self.app_mode == "demo"

