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
    
    upload_dir: str = "uploads"
    db_path: str = str(Path(__file__).parent / "expense_tracker.db")

    class Config:
        env_file = find_dotenv()
        extra = "ignore"
        populate_by_name = True

settings = Settings()
