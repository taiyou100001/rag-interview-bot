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