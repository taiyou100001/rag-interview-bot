# rag_service.py

import os
import json
import hashlib
import numpy as np
import redis
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# 引入必要的庫
from sentence_transformers import SentenceTransformer
import faiss
from pydantic import BaseModel, ValidationError
from backend.config import settings

# 設定 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic 模型 (用於資料驗證) ---
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
    difficulty_hint: str = None  # 新增：支援難度提示

    def to_dict(self):
        return self.dict()

# --- RagService 類別 (整合版) ---
class RagService:
    def __init__(self, cache_ttl=3600):
        # 使用 settings 路徑
        self.data_dir = Path(os.path.join(settings.BASE_DIR, "knowledge_base"))
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.items: List[KnowledgeItem] = []
        self.index = None
        self.cache_ttl = cache_ttl
        
        # 嘗試連線 Redis，若失敗則降級運行
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
        except Exception:
            logger.warning("Redis 連線失敗，RAG 將在無快取模式下運行")
            self.redis = None

        self._load_and_index()

    def _load_and_index(self):
        """載入知識庫並建立 FAISS 索引 (整合 HEAD 的邏輯與 Vivi 的路徑)"""
        if not self.data_dir.exists():
            logger.warning(f"知識庫不存在: {self.data_dir}")
            return

        texts = []
        # 使用 rglob 遞迴搜尋
        for file in self.data_dir.rglob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    parsed_items = self._parse_knowledge(data)
                    for item in parsed_items:
                        self.items.append(item)
                        texts.append(self._item_to_text(item))
            except Exception as e:
                logger.error(f"載入失敗 {file}: {e}")

        if texts:
            # 建立 FAISS 索引 (比 numpy.dot 更快)
            embeddings = self.model.encode(texts, show_progress_bar=False)
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dim)  # 內積相似度 (Inner Product)
            self.index.add(embeddings.astype(np.float32))
            logger.info(f"索引建立完成: {len(self.items)} 項")

    def _parse_knowledge(self, data: Dict) -> List[KnowledgeItem]:
        """解析 JSON 為 Pydantic 物件"""
        items = []
        pos = data.get("position", "")
        ind = data.get("industry", "")
        
        # 解析技能
        for skill in data.get("skill_areas", []):
            try:
                items.append(KnowledgeItem(
                    type="skill", position=pos, industry=ind,
                    area=skill.get("area"), importance=skill.get("importance"),
                    concepts=skill.get("key_concepts", []),
                    evaluation=skill.get("evaluation_points", []),
                    scenarios=skill.get("example_scenarios", []),
                    difficulty_hint=skill.get("difficulty_hint", "") # 嘗試讀取難度提示
                ))
            except ValidationError as e:
                logger.warning(f"技能驗證失敗: {e}")
        
        # 解析維度
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
        """將知識點轉為可嵌入的文字"""
        if item.type == "skill":
            return f"{item.area} {' '.join(item.concepts)} {' '.join(item.evaluation)}"
        return f"{item.dimension} {item.description} {' '.join(item.stages)}"

    def _cache_key(self, query: str) -> str:
        return f"rag:{hashlib.md5(query.encode()).hexdigest()}"

    def _fuzzy_match(self, job: str, position: str) -> bool:
        """模糊匹配職位名稱"""
        keywords = ['工程師', '設計師', '分析師', '管理', '企劃', '服務', '師', '員', 'Developer']
        job_lower = job.lower()
        pos_lower = position.lower()
        
        # 直接包含
        if job_lower in pos_lower or pos_lower in job_lower:
            return True
            
        # 關鍵字重疊
        for kw in keywords:
            if kw in job_lower and kw in pos_lower:
                return True
        return False

    # --- 主要檢索方法 (整合 AgentService 需求) ---
    def get_relevant_knowledge(self, query: str, job_title: str, difficulty: str = None, top_k: int = 2) -> List[Dict]:
        """
        根據查詢檢索相關知識
        """
        # 1. 檢查 Redis 快取
        cache_key = self._cache_key(f"{query}_{job_title}_{difficulty}")
        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        if not self.index:
            return []

        # 2. 向量搜尋
        q_emb = self.model.encode([query])
        # 搜尋多一點 (top_k * 5) 以便後續過濾
        D, I = self.index.search(q_emb.astype(np.float32), top_k * 5)

        results = []
        seen_ids = set()
        
        for idx, score in zip(I[0], D[0]):
            if idx == -1 or score < 0.3: continue # 過濾低相關性
            if idx in seen_ids: continue
            
            item = self.items[idx]
            
            # 3. 職位過濾 (整合 Vivi 的 _fuzzy_match)
            if not self._fuzzy_match(job_title, item.position):
                continue
                
            # 4. (可選) 難度過濾邏輯 - 這裡僅作為排序參考或 logging
            # 如果未來 KnowledgeItem 有 difficulty 欄位，可在此過濾
            
            results.append(item.to_dict())
            seen_ids.add(idx)
            
            if len(results) >= top_k:
                break

        # 5. 寫入快取
        if results and self.redis:
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(results))
            
        return results

    # --- 新功能 ---
    def search_by_resume_content(self, resume_text: str, job_title: str, top_k: int = 3) -> List[Dict]:
        """基於履歷內容檢索最相關的知識點 (適配 FAISS 版本)"""
        if not self.index:
            return []
        
        # 履歷向量化（取前500字避免太長）
        resume_emb = self.model.encode([resume_text[:500]])
        D, I = self.index.search(resume_emb.astype(np.float32), top_k * 5)
        
        results = []
        for idx, score in zip(I[0], D[0]):
            if idx == -1: continue
            item = self.items[idx]
            
            # 職位過濾
            if self._fuzzy_match(job_title, item.position):
                results.append(item.to_dict())
                if len(results) >= top_k:
                    break
        return results

    def is_question_similar(self, new_question: str, history: list, threshold: float = 0.85) -> bool:
        """檢查問題是否與歷史問題相似 (語意去重)"""
        if not history:
            return False
        
        new_emb = self.model.encode([new_question])[0]
        
        for turn in history:
            old_question = turn.get('question', '')
            if not old_question:
                continue
            
            old_emb = self.model.encode([old_question])[0]
            
            # 計算餘弦相似度
            similarity = np.dot(new_emb, old_emb) / (
                np.linalg.norm(new_emb) * np.linalg.norm(old_emb) + 1e-8
            )
            
            if similarity > threshold:
                return True
        
        return False