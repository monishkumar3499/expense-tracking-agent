from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import find_dotenv

class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    
    # Ollama Settings
    ollama_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:1.5b"
    ollama_ocr_model: str = "moondream:latest"
    
    upload_dir: str = "uploads"
    db_path: str = str(Path(__file__).parent / "expense_tracker.db")

    class Config:
        env_file = find_dotenv()
        extra = "ignore"

settings = Settings()
