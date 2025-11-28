# rag_engine.py
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
    difficulty_levels: Dict[str, str] = {}  # {'easy': '...', 'medium': '...', 'hard': '...'}
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
                # 解析 example_scenarios，支援舊格式（陣列）和新格式（含難度級別）
                example_scenarios_raw = skill.get("example_scenarios", [])
                scenarios = []
                difficulty_levels = {}
                
                if isinstance(example_scenarios_raw, dict):
                    # 新格式：{"scenarios": [...], "difficulty_levels": {...}}
                    scenarios = example_scenarios_raw.get("scenarios", [])
                    difficulty_levels = example_scenarios_raw.get("difficulty_levels", {})
                elif isinstance(example_scenarios_raw, list):
                    # 舊格式：[...]
                    scenarios = example_scenarios_raw
                
                items.append(KnowledgeItem(
                    type="skill", position=pos, industry=ind,
                    area=skill.get("area"), importance=skill.get("importance"),
                    concepts=skill.get("key_concepts", []),
                    evaluation=skill.get("evaluation_points", []),
                    scenarios=scenarios,
                    difficulty_levels=difficulty_levels
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
    
    def get_relevant_knowledge(self, query, job_title, top_k=2):
        # 只是呼叫原本的 get_relevant()，以應對呼叫get_relevant_knowledge(不知道在哪) 的需求
        return self.get_relevant(query, job_title, top_k)
    
    def get_relevant_knowledge_by_difficulty(self, query: str, job_title: str, difficulty: str = "medium", top_k: int = 2) -> List[Dict]:
        """根據難度級別搜尋相關知識
        
        Args:
            query: 搜尋關鍵詞
            job_title: 職位名稱
            difficulty: 難度級別 ('easy', 'medium', 'hard')
            top_k: 返回結果數量
        
        Returns:
            包含難度級別資訊的知識項目列表
        """
        cache_key = self._cache_key(f"{query}:{difficulty}")
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        if not self.index:
            return []

        q_emb = self.model.encode([query])
        D, I = self.index.search(q_emb.astype(np.float32), top_k * 3)

        results = []
        for idx, score in zip(I[0], D[0]):
            if score < 0.3: 
                continue
            item = self.items[idx]
            if job_title.lower() in item.position.lower() or item.position.lower() in job_title.lower():
                result_dict = item.dict()
                
                # 如果有難度級別資訊，加入難度相關的提示
                if item.difficulty_levels and difficulty in item.difficulty_levels:
                    result_dict["difficulty_hint"] = item.difficulty_levels[difficulty]
                    result_dict["current_difficulty"] = difficulty
                
                results.append(result_dict)
                if len(results) >= top_k:
                    break

        if results:
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(results))
        return results