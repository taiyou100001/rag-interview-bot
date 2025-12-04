import pytest
from unittest.mock import MagicMock, patch
from agents import JobInferenceAgent, QuestionGeneratorAgent

class TestJobInferenceAgent:
    @pytest.fixture
    def agent(self):
        return JobInferenceAgent()

    @patch('agents.ollama.chat')
    def test_infer_job_title_success(self, mock_chat, agent):
        # 模擬 Ollama 回傳
        mock_response = {'message': {'content': '應徵職位：後端工程師'}}
        mock_chat.return_value = mock_response

        resume_text = "熟悉 Python, Django, SQL..."
        result = agent.infer_job_title(resume_text)

        # 驗證結果是否正確清理了文字
        assert result == "後端工程師"
        
        # 修正：因為 ollama.chat 是用 kwargs 呼叫的，所以要從 kwargs 取得參數
        _, kwargs = mock_chat.call_args
        assert "熟悉 Python" in kwargs['messages'][1]['content']

    def test_infer_job_title_from_structured_data(self, agent):
        # 測試優先從結構化資料讀取
        structured = {'job_title': 'Frontend Developer'}
        result = agent.infer_job_title("text", structured)
        assert result == 'Frontend Developer'

class TestQuestionGeneratorAgent:
    @pytest.fixture
    def agent(self):
        return QuestionGeneratorAgent()

    @patch('agents.ollama.chat')
    def test_generate_question_format(self, mock_chat, agent):
        # 模擬回傳
        mock_chat.return_value = {'message': {'content': '請問您在過往專案中如何處理資料庫鎖死的問題？'}}
        
        history = []
        job = "軟體工程師"
        resume = "履歷內容..."

        question = agent.generate_question(job, resume, history)
        
        assert "資料庫" in question
        # 驗證轉換繁體中文的邏輯是否被觸發
        assert agent._convert_to_traditional("怎么") == "怎麼"