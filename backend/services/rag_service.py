# backend/services/rag_service.py
from sentence_transformers import SentenceTransformer
import faiss
import json
from pathlib import Path

class RAGService:
    def __init__(self):
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.index = None
        self.metadata = []
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        path = Path("knowledge_base")
        if not path.exists():
            return
        
        texts = []
        for file in path.rglob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    text = f"{data.get('position','')} {data.get('industry','')} " + " ".join([
                        area["area"] for skill in data.get("skill_areas", []) for area in [skill]
                    ])
                    texts.append(text)
                    self.metadata.append(data)
            except Exception as e:
                print(f"載入 {file} 失敗: {e}")
        
        if texts:
            embeddings = self.model.encode(texts)
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(embeddings.astype('float32'))

    def retrieve(self, query: str, top_k: int = 3):
        if not self.index or not self.metadata:
            return []
        query_vec = self.model.encode([query])
        D, I = self.index.search(query_vec.astype('float32'), top_k)
        return [self.metadata[i] for i in I[0] if i < len(self.metadata)]

# 必須有這行！
rag_service = RAGService()