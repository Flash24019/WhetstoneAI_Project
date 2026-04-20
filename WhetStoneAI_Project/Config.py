from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Whetstone AI Backend"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    ollama_host: str = "127.0.0.1"
    ollama_port: int = 11434
    ollama_model: str = "llama3.2:3b"

    ollama_startup_timeout: int = 30
    ollama_request_timeout: int = 120
    ollama_pull_timeout: int = 900

    allow_origins: list[str] = ["*"]

    @property
    def ollama_base_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"


settings = Settings()