# backend/services/speech_service.py
import azure.cognitiveservices.speech as speechsdk
from backend.config import settings
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzureSpeechService:
    """Azure 語音服務封裝 (單例模式)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化 Azure Speech SDK"""
        if self._initialized:
            return
        
        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=settings.AZURE_SPEECH_KEY,
                region=settings.AZURE_SPEECH_REGION
            )
            speech_config.speech_recognition_language = "zh-TW"
            speech_config.speech_synthesis_voice_name = "zh-TW-YunJheNeural"  # 台灣男聲
            
            self.speech_config = speech_config
            self._initialized = True
            logger.info("[Speech] Azure Speech Service 初始化成功")
            
        except Exception as e:
            logger.error(f"[Speech] 初始化失敗: {e}")
            raise

    def text_to_speech(self, text: str, output_path: str) -> str:
        """
        文字轉語音 (TTS)
        
        Args:
            text: 要合成的文字
            output_path: 輸出音檔路徑
            
        Returns:
            str: 音檔路徑
        """
        try:
            # 確保輸出資料夾存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 設定音檔輸出
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
            
            # 建立合成器
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )
            
            # 執行合成
            result = synthesizer.speak_text_async(text).get()
            
            # 檢查結果
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"[Speech] TTS 成功: {output_path}")
                return output_path
            else:
                error_msg = f"TTS 失敗: {result.cancellation_details.error_details}"
                logger.error(f"[Speech] {error_msg}")
                raise RuntimeError(error_msg)
                
        except Exception as e:
            logger.error(f"[Speech] TTS 錯誤: {e}")
            raise

    def speech_to_text(self, audio_path: str) -> str:
        """
        語音轉文字 (STT)
        
        Args:
            audio_path: 音檔路徑
            
        Returns:
            str: 辨識的文字 (若失敗回傳空字串)
        """
        try:
            # 設定音檔輸入
            audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
            
            # 建立辨識器
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )
            
            # 執行辨識
            result = recognizer.recognize_once()
            
            # 處理結果
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = result.text.strip()
                logger.info(f"[Speech] STT 成功: {text[:50]}...")
                return text
                
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logger.warning("[Speech] STT 未偵測到語音")
                return ""
                
            else:
                logger.error(f"[Speech] STT 失敗: {result.cancellation_details}")
                return ""
                
        except Exception as e:
            logger.error(f"[Speech] STT 錯誤: {e}")
            return ""


# ✅ 重點：建立全局實例
speech_service = AzureSpeechService()