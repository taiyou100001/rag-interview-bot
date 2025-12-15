# backend/services/ocr_service.py
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from backend.config import settings
import time

class OCRService:
    def __init__(self):
        self.client = ComputerVisionClient(
            endpoint=settings.AZURE_ENDPOINT,
            credentials=CognitiveServicesCredentials(settings.AZURE_SUBSCRIPTION_KEY)
        )

    def process_file(self, file_path: str):
        with open(file_path, "rb") as f:
            read_response = self.client.read_in_stream(f, raw=True)
        
        operation_location = read_response.headers["Operation-Location"]
        operation_id = operation_location.split("/")[-1]

        while True:
            result = self.client.get_read_result(operation_id)
            if result.status not in ['notStarted', 'running']:
                break
            time.sleep(1)

        if result.status == "succeeded":
            return True, result.as_dict()
        else:
            return False, {"error": f"OCR 失敗，狀態：{result.status}"}

# 必須有這行！
ocr_service = OCRService()