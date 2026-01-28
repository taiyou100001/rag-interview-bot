# backend/services/speech_service.py
import azure.cognitiveservices.speech as speechsdk
from backend.config import settings
import logging
import os
import threading# 新增：用於等待辨識完成

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
            
            # 用於同步等待辨識結束的旗標
            done_event = threading.Event()
            all_results = []

            # 3. 定義回呼函式 (Callback Functions)
            def stop_cb(evt):
                """當 session 停止或取消時觸發"""
                logger.info(f'[Speech] 辨識結束或取消: {evt}')
                done_event.set()  # 解除等待

            def recognized_cb(evt):
                """每辨識完一句話觸發"""
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    logger.info(f'[Speech] 辨識句段: {evt.result.text}')
                    all_results.append(evt.result.text)

            # 4. 連接事件
            recognizer.recognized.connect(recognized_cb)
            recognizer.session_stopped.connect(stop_cb)
            recognizer.canceled.connect(stop_cb)

            # 5. 開始連續辨識 (Continuous Recognition)
            logger.info(f"[Speech] 開始連續辨識音檔: {audio_path}")
            recognizer.start_continuous_recognition()

            # 6. 等待辨識完成
            # 對於檔案輸入，Azure 讀完檔案會自動觸發 session_stopped，所以我們可以一直等
            # 這裡不設 timeout，因為如果檔案很長，30秒會不夠，改讓 Azure 自己通知結束
            done_event.wait() 

            # 7. 停止辨識並釋放資源
            recognizer.stop_continuous_recognition()
            
            # 8. 組合結果
            final_text = "".join(all_results)
            
            if not final_text:
                logger.warning("[Speech] STT 完成但沒有辨識到文字")
                
            return final_text
                
        except Exception as e:
            logger.error(f"[Speech] STT 發生錯誤: {e}")
            return ""

# ✅ 建立全局實例
speech_service = AzureSpeechService()
