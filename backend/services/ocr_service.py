# backend/services/ocr_service.py
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from backend.config import settings
import time

class OCRService:
    """Azure OCR 服務封裝"""
    
    def __init__(self):
        """初始化 Azure Computer Vision 客戶端"""
        self.client = ComputerVisionClient(
            endpoint=settings.AZURE_ENDPOINT,
            credentials=CognitiveServicesCredentials(settings.AZURE_SUBSCRIPTION_KEY)
        )

    def process_file(self, file_path: str):
        """
        處理上傳的檔案並進行 OCR 辨識
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            tuple: (success: bool, result: dict)
        """
        try:
            with open(file_path, "rb") as f:
                read_response = self.client.read_in_stream(f, raw=True)
            
            # 取得操作位置
            operation_location = read_response.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]

            # 等待 OCR 完成
            while True:
                result = self.client.get_read_result(operation_id)
                if result.status not in ['notStarted', 'running']:
                    break
                time.sleep(1)

            # 檢查結果
            if result.status == "succeeded":
                return True, result.as_dict()
            else:
                return False, {"error": f"OCR 失敗，狀態：{result.status}"}
                
        except Exception as e:
            return False, {"error": f"OCR 處理錯誤: {str(e)}"}


# ✅ 重點：必須建立全局實例
ocr_service = OCRService()