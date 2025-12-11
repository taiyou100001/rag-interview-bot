# speech_service.py

import os
import uuid
import azure.cognitiveservices.speech as speechsdk
from backend.config import settings

class SpeechService:
    def __init__(self):
        # 設定 Azure 語音組態
        self.speech_config = speechsdk.SpeechConfig(
            subscription=settings.AZURE_SPEECH_KEY, 
            region=settings.AZURE_SPEECH_REGION
        )
        # 設定中文語音 (台灣)
        self.speech_config.speech_synthesis_voice_name = "zh-TW-YunJheNeural" 
        self.speech_config.speech_recognition_language = "zh-TW" # 設定辨識語言

    def text_to_speech(self, text: str) -> str:
        """
        將文字轉為語音檔案，並回傳相對 URL
        """
        filename = f"{uuid.uuid4()}.wav"
        file_path = os.path.join(settings.AUDIO_DIR, filename)
        
        # 設定輸出到檔案
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_path)
        
        # 建立合成器
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config, 
            audio_config=audio_config
        )
        
        # 開始合成
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # 回傳給前端的相對路徑 (對應 main.py 的 static mount)
            return f"/static/audio/{filename}"
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"語音合成取消: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"錯誤詳情: {cancellation_details.error_details}")
            return ""
        
        return ""
    
    def speech_to_text(self, audio_file_path: str) -> str:
        """
        將 wav 音檔轉為文字 (STT)
        """
        audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config, 
            audio_config=audio_config
        )

        print("正在進行語音辨識...")
        result = speech_recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f"辨識結果: {result.text}")
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print("無法辨識語音")
            return ""
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"語音辨識取消: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"錯誤詳情: {cancellation_details.error_details}")
            return ""
        
        return ""
    