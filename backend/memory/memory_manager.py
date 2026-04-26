import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
import os
import uuid

# Local embedding function
# This uses a small, fast model (all-MiniLM-L6-v2) suitable for local CPU execution
try:
    default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
except Exception as e:
    print(f"⚠️ [MEMORY] Could not initialize SentenceTransformer: {e}")
    default_ef = None

class MemoryManager:
    def __init__(self, persist_directory: str = None):
        if persist_directory is None:
            # Absolute path to ensure it works from any CWD
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            persist_directory = os.path.join(base_dir, "memory", "chroma_db")
        
        os.makedirs(persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="user_insights",
            embedding_function=default_ef,
            metadata={"hnsw:space": "cosine"}
        )

    def add_insight(self, insight: str, metadata: Dict[str, Any] = None):
        """Adds a clean distilled insight to the long-term vector memory."""
        if not insight or insight.strip().lower() == "none":
            return
            
        print(f"🧠 [MEMORY] Archiving insight: {insight}")
        self.collection.add(
            documents=[insight.strip()],
            ids=[str(uuid.uuid4())],
            metadatas=[metadata or {"type": "insight", "timestamp": os.getenv("CURRENT_TIME", "")}]
        )

    def search_memory(self, query: str, limit: int = 5, threshold: float = 0.6) -> List[str]:
        """Searches for relevant insights based on semantic similarity to the query."""
        if not query:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        filtered_docs = []
        if results['documents'] and results['distances']:
            for doc, dist in zip(results['documents'][0], results['distances'][0]):
                similarity = 1 - dist
                print(f"DEBUG: Found Insight: '{doc[:50]}...' | Score: {similarity:.2f}")
                if similarity >= threshold:
                    filtered_docs.append(doc)
        
        if filtered_docs:
            print(f"🧠 [MEMORY] Retrieved {len(filtered_docs)} relevant insights from RAG.")
            
        return filtered_docs

# Singleton instance for easy import
memory_manager = MemoryManager()
