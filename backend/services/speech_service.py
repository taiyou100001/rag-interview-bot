# backend/services/speech_service.py
import azure.cognitiveservices.speech as speechsdk
from backend.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzureSpeechService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            speech_config = speechsdk.SpeechConfig(
                subscription=settings.AZURE_SPEECH_KEY,
                region=settings.AZURE_SPEECH_REGION
            )
            speech_config.speech_recognition_language = "zh-TW"
            speech_config.speech_synthesis_voice_name = "zh-TW-YunJheNeural"  # 台灣男聲
            cls._instance.speech_config = speech_config
            logger.info("Azure Speech Service 初始化成功")
        return cls._instance

    def text_to_speech(self, text: str, output_path: str) -> str:
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )
        result = synthesizer.speak_text_async(text).get()
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            raise RuntimeError(f"TTS 失敗: {result.error_details}")
        return output_path

    def speech_to_text(self, audio_path: str) -> str:
        audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )
        result = recognizer.recognize_once()
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text.strip()
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return ""
        else:
            logger.error(f"STT 失敗: {result.cancellation_details}")
            return ""

# 必須有這行！
speech_service = AzureSpeechService()