from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import find_dotenv

class Settings(BaseSettings):
    # Model Settings (Configurable via .env)
    ollama_url: str = "http://localhost:11434"
    model_name: str = Field(default="qwen2.5:1.5b", alias="MODEL") 
    use_local_llm: bool = Field(default=False, alias="USE_LOCAL_LLM")
    
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    
    upload_dir: str = "uploads"
    db_path: str = str(Path(__file__).parent / "expense_tracker.db")

    class Config:
        env_file = find_dotenv()
        extra = "ignore"
        populate_by_name = True

settings = Settings()

# Startup Diagnostic
if not settings.mistral_api_key:
    print("⚠️ [CONFIG] Warning: MISTRAL_API_KEY is empty. OCR will fail.")
else:
    print(f"✅ [CONFIG] Mistral Key detected: {settings.mistral_api_key[:4]}...{settings.mistral_api_key[-4:]}")

if not settings.google_api_key:
    print("⚠️ [CONFIG] Warning: GOOGLE_API_KEY is empty.")
else:
    print(f"✅ [CONFIG] Google Key detected: {settings.google_api_key[:4]}...{settings.google_api_key[-4:]}")
