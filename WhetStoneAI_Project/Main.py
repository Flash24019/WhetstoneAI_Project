from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from Config import settings
from Logger import logger
from Ollama import OllamaSetupError, bootstrap_ollama, improve_with_ollama


app = FastAPI(title=settings.app_name)

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_home():
    return FileResponse("index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ollama_state: dict = {}


class ImproveRequest(BaseModel):
    draft: str = Field(..., min_length=1)
    tone: Literal["Professional", "Academic", "Casual", "Persuasive"]


class ImproveResponse(BaseModel):
    subject: str
    improved_version: str
    feedback: list[str]


@app.on_event("startup")
def startup_event() -> None:
    global ollama_state

    try:
        ollama_state = bootstrap_ollama()
        logger.info(f"Startup complete: {ollama_state}")
    except OllamaSetupError as exc:
        ollama_state = {"error": str(exc)}
        logger.exception("Ollama startup failed.")


@app.get("/health")
def health() -> dict:
    if "error" in ollama_state:
        return {"status": "error", "message": ollama_state["error"]}

    return {
        "status": "ok",
        "ollama": ollama_state
    }


@app.post("/api/improve", response_model=ImproveResponse)
def improve_writing(payload: ImproveRequest) -> ImproveResponse:
    if "error" in ollama_state:
        raise HTTPException(status_code=503, detail=ollama_state["error"])

    try:
        result = improve_with_ollama(
            base_url=ollama_state["base_url"],
            model=ollama_state["model"],
            draft=payload.draft,
            tone=payload.tone
        )
    except OllamaSetupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during improve request.")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while improving the writing."
        ) from exc

    subject = str(result.get("subject", "")).strip()
    improved_version = str(result.get("improved_version", "")).strip()
    feedback = result.get("feedback", [])

    if not subject or not improved_version or not isinstance(feedback, list):
        logger.error(f"Incomplete model response: {result}")
        raise HTTPException(
            status_code=502,
            detail="The local AI returned an incomplete response."
        )

    return ImproveResponse(
        subject=subject,
        improved_version=improved_version,
        feedback=[str(item) for item in feedback]
    )