<<<<<<< HEAD
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
=======
# knowledge_rag.py (增強版 - 加入履歷檢索和去重) rag_services.py
from sentence_transformers import SentenceTransformer
import numpy as np
import json
import os
from backend.config import settings

class RagService:
    # 將預設值改為 '../knowledge_base'
    def __init__(self):
        self.data_dir = os.path.join(settings.BASE_DIR, "knowledge_base")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        self.knowledge_items = []
        self.embeddings = None
        
        self._load_knowledge()
        if self.knowledge_items:
            self._build_embeddings()
    
    def _load_knowledge(self):
        """載入知識庫"""
        if not os.path.exists(self.data_dir):
            print(f"知識庫目錄不存在: {self.data_dir}")
            return
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.json'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self._parse_knowledge(data)
                    except Exception as e:
                        print(f"警告: 無法載入 {filepath}: {e}")
        
        print(f"✓ 載入 {len(self.knowledge_items)} 個知識點")
    
    def _parse_knowledge(self, data):
        """解析知識庫資料"""
        position = data.get('position', '')
        industry = data.get('industry', '')
        
        # 技能領域
        for skill in data.get('skill_areas', []):
            self.knowledge_items.append({
                'type': 'skill',
                'position': position,
                'industry': industry,
                'area': skill.get('area', ''),
                'importance': skill.get('importance', ''),
                'concepts': skill.get('key_concepts', []),
                'evaluation': skill.get('evaluation_points', []),
                'scenarios': skill.get('example_scenarios', [])
            })
        
        # 面試維度
        for dim in data.get('interview_dimensions', []):
            self.knowledge_items.append({
                'type': 'dimension',
                'position': position,
                'industry': industry,
                'dimension': dim.get('dimension', ''),
                'stages': dim.get('stages', []),
                'description': dim.get('description', '')
            })
    
    def _build_embeddings(self):
        """建立向量索引"""
        texts = []
        for item in self.knowledge_items:
            if item['type'] == 'skill':
                text = f"{item['area']} {' '.join(item['concepts'])} {' '.join(item['evaluation'])}"
            else:
                text = f"{item['dimension']} {item['description']} {' '.join(item['stages'])}"
            texts.append(text)
        
        self.embeddings = self.model.encode(texts, show_progress_bar=False)
        print(f"✓ 向量索引建立完成")
    
    def get_relevant_knowledge(self, query: str, job_title: str, top_k: int = 2):
        """檢索相關知識點"""
        if not self.knowledge_items or self.embeddings is None:
            return []
        
        # 向量檢索
        query_embedding = self.model.encode([query])[0]
        similarities = np.dot(self.embeddings, query_embedding)
        
        # 過濾職位（模糊匹配）
        filtered = []
        for idx, item in enumerate(self.knowledge_items):
            pos = item['position'].lower()
            job = job_title.lower()
            
            if job in pos or pos in job or self._fuzzy_match(job, pos):
                filtered.append((idx, similarities[idx]))
        
        # 如果沒有匹配，返回最相似的
        if not filtered:
            top_indices = np.argsort(similarities)[::-1][:top_k]
            return [self.knowledge_items[idx] for idx in top_indices]
        
        # 排序並返回
        filtered.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in filtered[:top_k]]
        
        return [self.knowledge_items[idx] for idx in top_indices]
    
    def search_by_resume_content(self, resume_text: str, job_title: str, top_k: int = 3):
        """基於履歷內容檢索最相關的知識點"""
        if not self.knowledge_items or self.embeddings is None:
            return []
        
        # 履歷向量化（取前500字避免太長）
        resume_embedding = self.model.encode([resume_text[:500]])[0]
        
        # 計算相似度
        similarities = np.dot(self.embeddings, resume_embedding)
        
        # 過濾職位
        filtered = []
        for idx, item in enumerate(self.knowledge_items):
            pos = item['position'].lower()
            job = job_title.lower()
            if job in pos or pos in job:
                filtered.append((idx, similarities[idx]))
        
        if not filtered:
            top_indices = np.argsort(similarities)[::-1][:top_k]
            return [self.knowledge_items[idx] for idx in top_indices]
        
        # 排序返回
        filtered.sort(key=lambda x: x[1], reverse=True)
        return [self.knowledge_items[idx] for idx, _ in filtered[:top_k]]
    
    def is_question_similar(self, new_question: str, history: list, threshold: float = 0.85) -> bool:
        """檢查問題是否與歷史問題相似（避免重複）"""
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
    
    def _fuzzy_match(self, job: str, position: str) -> bool:
        """模糊匹配職位名稱"""
        keywords = ['工程師', '設計師', '分析師', '管理', '企劃', '服務', '師', '員']
        for kw in keywords:
            if kw in job and kw in position:
                return True
        return False
>>>>>>> origin/Vivi
