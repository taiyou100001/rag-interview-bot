# backend/services/enhanced_speech_service.py
import azure.cognitiveservices.speech as speechsdk
from backend.config import settings
import logging
import os
import threading
import json
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedAzureSpeechService:
    """
    增強版 Azure 語音服務
    新增功能：
    1. 信心分數記錄
    2. 辨識品質監控
    3. 詳細錯誤日誌
    """
    
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
            speech_config.speech_synthesis_voice_name = "zh-TW-YunJheNeural"
            
            # 啟用詳細輸出（包含信心分數）
            speech_config.output_format = speechsdk.OutputFormat.Detailed
            
            self.speech_config = speech_config
            self._initialized = True
            
            # 初始化統計資料
            self.stats = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "avg_confidence": 0.0,
                "low_confidence_count": 0
            }
            
            logger.info("[Enhanced Speech] Azure Speech Service 初始化成功")
            
        except Exception as e:
            logger.error(f"[Enhanced Speech] 初始化失敗: {e}")
            raise

    def text_to_speech(self, text: str, output_path: str) -> str:
        """
        文字轉語音 (TTS) - 保持原有功能
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )
            
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"[Enhanced Speech] TTS 成功: {output_path}")
                return output_path
            else:
                error_msg = f"TTS 失敗: {result.cancellation_details.error_details}"
                logger.error(f"[Enhanced Speech] {error_msg}")
                raise RuntimeError(error_msg)
                
        except Exception as e:
            logger.error(f"[Enhanced Speech] TTS 錯誤: {e}")
            raise

    def speech_to_text_with_confidence(self, audio_path: str) -> Dict:
        """
        語音轉文字 (STT) - 增強版，包含信心分數
        
        Args:
            audio_path: 音檔路徑
            
        Returns:
            Dict: {
                "text": 辨識文字,
                "confidence": 信心分數 (0-1),
                "duration": 音檔時長,
                "word_details": 逐字信心分數列表,
                "quality": 品質評級 (high/medium/low)
            }
        """
        try:
            self.stats["total_requests"] += 1
            
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
            all_confidences = []
            word_details = []

            def stop_cb(evt):
                """當 session 停止或取消時觸發"""
                logger.info(f'[Enhanced Speech] 辨識結束: {evt}')
                done_event.set()

            def recognized_cb(evt):
                """每辨識完一句話觸發"""
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    text = evt.result.text
                    all_results.append(text)
                    
                    # 提取信心分數（從詳細結果）
                    try:
                        import json
                        detailed = json.loads(evt.result.json)
                        
                        # NBest[0] 包含最佳辨識結果
                        if 'NBest' in detailed and len(detailed['NBest']) > 0:
                            best = detailed['NBest'][0]
                            confidence = best.get('Confidence', 0.0)
                            all_confidences.append(confidence)
                            
                            # 提取逐字信心分數
                            if 'Words' in best:
                                for word_info in best['Words']:
                                    word_details.append({
                                        "word": word_info.get('Word', ''),
                                        "confidence": word_info.get('Confidence', 0.0)
                                    })
                            
                            logger.info(f'[Enhanced Speech] 辨識: {text} (信心分數: {confidence:.2f})')
                    except Exception as e:
                        logger.warning(f"[Enhanced Speech] 無法解析信心分數: {e}")
                        all_confidences.append(1.0)  # 預設值

            # 連接事件
            recognizer.recognized.connect(recognized_cb)
            recognizer.session_stopped.connect(stop_cb)
            recognizer.canceled.connect(stop_cb)

            # 開始連續辨識
            logger.info(f"[Enhanced Speech] 開始辨識: {audio_path}")
            recognizer.start_continuous_recognition()
            done_event.wait()
            recognizer.stop_continuous_recognition()
            
            # 組合結果
            final_text = "".join(all_results)
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            # 判斷品質等級
            if avg_confidence >= 0.9:
                quality = "high"
            elif avg_confidence >= 0.7:
                quality = "medium"
            else:
                quality = "low"
                self.stats["low_confidence_count"] += 1
            
            # 更新統計
            if final_text:
                self.stats["successful_requests"] += 1
                self.stats["avg_confidence"] = (
                    (self.stats["avg_confidence"] * (self.stats["successful_requests"] - 1) + avg_confidence)
                    / self.stats["successful_requests"]
                )
            else:
                self.stats["failed_requests"] += 1
            
            result = {
                "text": final_text,
                "confidence": round(avg_confidence, 3),
                "word_details": word_details,
                "quality": quality,
                "audio_path": audio_path,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # 記錄到日誌檔
            self._log_recognition_result(result)
            
            if not final_text:
                logger.warning("[Enhanced Speech] STT 完成但沒有辨識到文字")
            
            return result
                
        except Exception as e:
            logger.error(f"[Enhanced Speech] STT 發生錯誤: {e}")
            self.stats["failed_requests"] += 1
            return {
                "text": "",
                "confidence": 0.0,
                "word_details": [],
                "quality": "failed",
                "error": str(e)
            }
    
    def _log_recognition_result(self, result: Dict):
        """將辨識結果記錄到日誌檔"""
        log_dir = "logs/stt_recognition"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"stt_log_{datetime.now().strftime('%Y%m%d')}.jsonl")
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"[Enhanced Speech] 日誌寫入失敗: {e}")
    
    def get_statistics(self) -> Dict:
        """取得 STT 服務統計資料"""
        success_rate = (
            self.stats["successful_requests"] / self.stats["total_requests"] * 100
            if self.stats["total_requests"] > 0 else 0
        )
        
        return {
            **self.stats,
            "success_rate": round(success_rate, 2)
        }
    
    def speech_to_text(self, audio_path: str) -> str:
        """
        向後相容的 STT 方法（僅返回文字）
        """
        result = self.speech_to_text_with_confidence(audio_path)
        return result.get("text", "")


# 建立全局實例
enhanced_speech_service = EnhancedAzureSpeechService()