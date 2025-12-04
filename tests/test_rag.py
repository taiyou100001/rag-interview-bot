# tests/test_rag.py
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from knowledge_rag import KnowledgeRAGEngine

class TestKnowledgeRAGEngine:
    @pytest.fixture
    def mock_model(self):
        with patch('knowledge_rag.SentenceTransformer') as mock:
            model_instance = mock.return_value
            # 設定 encode 回傳假向量 (假設維度為 3)
            # 這裡回傳一個固定的 numpy array
            model_instance.encode.return_value = np.array([[0.1, 0.2, 0.3]])
            yield model_instance

    @pytest.fixture
    def rag_engine(self, mock_model):
        # 初始化時不載入真實檔案，手動注入資料
        engine = KnowledgeRAGEngine(data_dir="dummy_path")
        engine.knowledge_items = [
            {
                'type': 'skill',
                'position': '後端工程師',
                'industry': '科技',
                'area': '資料庫',
                'concepts': ['SQL'],
                'evaluation': [],
                'scenarios': []
            },
            {
                'type': 'dimension',
                'position': 'PM',
                'industry': '商業',
                'dimension': '溝通',
                'stages': [],
                'description': '溝通能力'
            }
        ]
        # 假裝已經建立好索引 (兩個項目)
        engine.embeddings = np.array([
            [1.0, 0.0, 0.0], # 向量 A
            [0.0, 1.0, 0.0]  # 向量 B
        ])
        return engine

    def test_fuzzy_match(self, rag_engine):
        assert rag_engine._fuzzy_match("資深後端工程師", "後端工程師") is True
        assert rag_engine._fuzzy_match("行銷人員", "後端工程師") is False

    def test_is_question_similar(self, rag_engine, mock_model):
        # 模擬：新問題與歷史問題非常相似 (向量相同)
        mock_model.encode.side_effect = [
            np.array([1.0, 0.0, 0.0]), # 新問題向量
            np.array([1.0, 0.0, 0.0])  # 歷史問題向量
        ]
        
        history = [{'question': 'Old Question'}]
        is_sim = rag_engine.is_question_similar("New Question", history, threshold=0.8)
        assert is_sim is True

    def test_is_question_different(self, rag_engine, mock_model):
        # 模擬：新問題與歷史問題完全垂直 (不相似)
        mock_model.encode.side_effect = [
            np.array([1.0, 0.0, 0.0]), 
            np.array([0.0, 1.0, 0.0])
        ]
        
        history = [{'question': 'Old Question'}]
        is_sim = rag_engine.is_question_similar("New Question", history, threshold=0.8)
        assert is_sim is False
