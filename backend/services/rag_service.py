# backend/services/rag_service.py
from sentence_transformers import SentenceTransformer
import faiss
import json
from pathlib import Path
import numpy as np

class RAGService:
    """RAG (Retrieval-Augmented Generation) 服務"""
    
    def __init__(self):
        """初始化向量模型與知識庫"""
        print("[RAG] 正在載入向量模型...")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.index = None
        self.metadata = []
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """載入知識庫並建立向量索引"""
        path = Path("knowledge_base")
        
        if not path.exists():
            print("[RAG] 警告: knowledge_base 資料夾不存在，跳過載入")
            return
        
        texts = []
        json_files = list(path.rglob("*.json"))
        
        if not json_files:
            print("[RAG] 警告: knowledge_base 中無 JSON 檔案")
            return
        
        print(f"[RAG] 找到 {len(json_files)} 個知識庫檔案")
        
        for file in json_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 組合文字用於向量化
                    position = data.get('position', '')
                    industry = data.get('industry', '')
                    skills = []
                    
                    for skill_area in data.get("skill_areas", []):
                        skills.extend(skill_area.get("key_concepts", []))
                    
                    text = f"{position} {industry} {' '.join(skills)}"
                    texts.append(text)
                    self.metadata.append(data)
                    
            except Exception as e:
                print(f"[RAG] 載入 {file} 失敗: {e}")
        
        if not texts:
            print("[RAG] 警告: 無有效知識庫資料")
            return
        
        # 建立 FAISS 向量索引
        print(f"[RAG] 正在建立向量索引 ({len(texts)} 筆資料)...")
        embeddings = self.model.encode(texts)
        dimension = embeddings.shape[1]
        
        self.index = faiss.IndexFlatIP(dimension)  # 使用內積 (Inner Product)
        
        # 正規化向量 (讓內積等同於餘弦相似度)
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings.astype('float32'))
        
        print(f"[RAG] 向量索引建立完成！")

    def retrieve(self, query: str, top_k: int = 3):
        """
        檢索相關知識
        
        Args:
            query: 查詢文字 (例如: "後端工程師 Python FastAPI")
            top_k: 回傳前 k 筆最相關資料
            
        Returns:
            list: 相關知識的 metadata
        """
        if not self.index or not self.metadata:
            print("[RAG] 警告: 向量索引未建立")
            return []
        
        # 將查詢轉為向量
        query_vec = self.model.encode([query])
        faiss.normalize_L2(query_vec)
        
        # 搜尋最相似的向量
        D, I = self.index.search(query_vec.astype('float32'), top_k)
        
        # 回傳對應的 metadata
        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(self.metadata):
                result = self.metadata[idx].copy()
                result['similarity_score'] = float(score)  # 加入相似度分數
                results.append(result)
        
        return results
    
    def get_position_knowledge(self, position: str):
        """
        取得特定職位的完整知識
        
        Args:
            position: 職位名稱 (例如: "後端工程師")
            
        Returns:
            dict or None: 職位知識
        """
        for data in self.metadata:
            if data.get('position') == position:
                return data
        return None


# ✅ 重點：建立全局實例
rag_service = RAGService()