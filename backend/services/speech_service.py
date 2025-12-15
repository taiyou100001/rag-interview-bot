# speech_service.py

import azure.cognitiveservices.speech as speechsdk
from backend.config import settings

class SpeechService:
    def __init__(self):
        # 設定 Azure 語音組態 (STT 需要)
        self.speech_config = speechsdk.SpeechConfig(
            subscription=settings.AZURE_SPEECH_KEY, 
            region=settings.AZURE_SPEECH_REGION
        )
        self.speech_config.speech_recognition_language = "zh-TW" # 設定辨識語言

    def speech_to_text(self, audio_file_path: str) -> str:
        """
        將 wav 音檔轉為文字 (STT)
        """
        # 設定音訊輸入來自檔案
        audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)
        
        # 建立辨識器
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config, 
            audio_config=audio_config
        )

        print(f"正在辨識音檔: {audio_file_path}")
        try:
            # 使用 recognize_once_async 進行單次辨識
            result = speech_recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                print(f"STT 結果: {result.text}")
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                print("STT 無法辨識語音 (NoMatch)")
                return ""
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                print(f"STT 取消: {cancellation.reason}, Error: {cancellation.error_details}")
                return ""
        except Exception as e:
            print(f"STT 發生例外狀況: {e}")
            return ""
        
        return ""
    