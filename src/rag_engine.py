# rag_engine.py rag_service.py
import os
import json
import hashlib
from typing import List, Dict, Any
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import redis
from pydantic import BaseModel, ValidationError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeItem(BaseModel):
    type: str  # 'skill' or 'dimension'
    position: str
    industry: str
    area: str = None
    importance: str = None
    concepts: List[str] = []
    evaluation: List[str] = []
    scenarios: List[str] = []
    dimension: str = None
    stages: List[str] = []
    description: str = None

class RAGEngine:
    def __init__(self, data_dir="knowledge_base", cache_ttl=3600):
        self.data_dir = Path(data_dir)
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.items: List[KnowledgeItem] = []
        self.index = None
        self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.cache_ttl = cache_ttl
        self._load_and_index()

    def _load_and_index(self):
        if not self.data_dir.exists():
            logger.warning(f"知識庫不存在: {self.data_dir}")
            return

        texts = []
        for file in self.data_dir.rglob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in self._parse_knowledge(data):
                        self.items.append(item)
                        texts.append(self._item_to_text(item))
            except Exception as e:
                logger.error(f"載入失敗 {file}: {e}")

        if texts:
            embeddings = self.model.encode(texts, show_progress_bar=True)
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dim)  # 內積相似度
            self.index.add(embeddings.astype(np.float32))
            logger.info(f"索引建立完成: {len(self.items)} 項")

    def _parse_knowledge(self, data: Dict) -> List[KnowledgeItem]:
        items = []
        pos = data.get("position", "")
        ind = data.get("industry", "")
        for skill in data.get("skill_areas", []):
            try:
                items.append(KnowledgeItem(
                    type="skill", position=pos, industry=ind,
                    area=skill.get("area"), importance=skill.get("importance"),
                    concepts=skill.get("key_concepts", []),
                    evaluation=skill.get("evaluation_points", []),
                    scenarios=skill.get("example_scenarios", [])
                ))
            except ValidationError as e:
                logger.warning(f"技能驗證失敗: {e}")
        for dim in data.get("interview_dimensions", []):
            try:
                items.append(KnowledgeItem(
                    type="dimension", position=pos, industry=ind,
                    dimension=dim.get("dimension"), stages=dim.get("stages", []),
                    description=dim.get("description", "")
                ))
            except ValidationError as e:
                logger.warning(f"維度驗證失敗: {e}")
        return items

    def _item_to_text(self, item: KnowledgeItem) -> str:
        if item.type == "skill":
            return f"{item.area} {' '.join(item.concepts)} {' '.join(item.evaluation)}"
        return f"{item.dimension} {item.description} {' '.join(item.stages)}"

    def _cache_key(self, query: str) -> str:
        return f"rag:{hashlib.md5(query.encode()).hexdigest()}"

    def get_relevant(self, query: str, job_title: str, top_k: int = 2) -> List[Dict]:
        cache_key = self._cache_key(query)
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        if not self.index:
            return []

        q_emb = self.model.encode([query])
        D, I = self.index.search(q_emb.astype(np.float32), top_k * 3)

        results = []
        for idx, score in zip(I[0], D[0]):
            if score < 0.3: continue
            item = self.items[idx]
            if job_title.lower() in item.position.lower() or item.position.lower() in job_title.lower():
                results.append(item.dict())
                if len(results) >= top_k:
                    break

        if results:
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(results))
        return results