# scripts/batch_stt_test.py
"""
STT 批次測試腳本
用於評估 STT 服務的整體準確率
"""
import os
import sys
import json
from pathlib import Path
from typing import List, Dict
import logging
from datetime import datetime

# 添加專案根目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

from backend.services.enhanced_speech_service import enhanced_speech_service
from backend.services.stt_metrics import STTMetrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class STTBatchTester:
    """STT 批次測試器"""
    
    def __init__(self, test_data_path: str, audio_dir: str):
        """
        初始化測試器
        
        Args:
            test_data_path: ground_truth.json 路徑
            audio_dir: 測試音檔目錄
        """
        self.test_data_path = test_data_path
        self.audio_dir = audio_dir
        self.results = []
        
    def load_test_data(self) -> List[Dict]:
        """載入測試資料"""
        try:
            with open(self.test_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("test_cases", [])
        except Exception as e:
            logger.error(f"載入測試資料失敗: {e}")
            return []
    
    def run_test(self) -> Dict:
        """執行批次測試"""
        test_cases = self.load_test_data()
        
        if not test_cases:
            logger.error("沒有測試資料")
            return {}
        
        print("\n" + "="*70)
        print("🧪 STT 批次測試開始")
        print("="*70)
        print(f"測試案例數量: {len(test_cases)}")
        print(f"音檔目錄: {self.audio_dir}\n")
        
        total_wer = 0
        total_cer = 0
        total_confidence = 0
        success_count = 0
        
        for i, case in enumerate(test_cases, 1):
            audio_file = case.get("audio_file")
            reference = case.get("reference_text")
            category = case.get("category", "general")
            
            audio_path = os.path.join(self.audio_dir, audio_file)
            
            print(f"\n【測試 {i}/{len(test_cases)}】")
            print(f"類別: {category}")
            print(f"音檔: {audio_file}")
            print(f"參考文字: {reference}")
            
            # 檢查音檔是否存在
            if not os.path.exists(audio_path):
                print(f"⚠️  音檔不存在: {audio_path}")
                self.results.append({
                    "test_id": i,
                    "audio_file": audio_file,
                    "reference": reference,
                    "hypothesis": "",
                    "status": "file_not_found",
                    "error": "音檔不存在"
                })
                continue
            
            # 執行 STT
            try:
                stt_result = enhanced_speech_service.speech_to_text_with_confidence(audio_path)
                hypothesis = stt_result.get("text", "")
                confidence = stt_result.get("confidence", 0.0)
                quality = stt_result.get("quality", "unknown")
                
                print(f"辨識結果: {hypothesis}")
                print(f"信心分數: {confidence:.3f} ({quality})")
                
                # 計算準確率
                metrics = STTMetrics.calculate_accuracy(reference, hypothesis)
                
                print(f"WER: {metrics['wer']}%")
                print(f"CER: {metrics['cer']}%")
                print(f"詞準確率: {metrics['word_accuracy']}%")
                print(f"字準確率: {metrics['char_accuracy']}%")
                
                # 累計統計
                total_wer += metrics['wer']
                total_cer += metrics['cer']
                total_confidence += confidence
                success_count += 1
                
                # 儲存結果
                self.results.append({
                    "test_id": i,
                    "audio_file": audio_file,
                    "category": category,
                    "reference": reference,
                    "hypothesis": hypothesis,
                    "confidence": confidence,
                    "quality": quality,
                    "wer": metrics['wer'],
                    "cer": metrics['cer'],
                    "word_accuracy": metrics['word_accuracy'],
                    "char_accuracy": metrics['char_accuracy'],
                    "status": "success"
                })
                
            except Exception as e:
                print(f"❌ 測試失敗: {e}")
                self.results.append({
                    "test_id": i,
                    "audio_file": audio_file,
                    "reference": reference,
                    "hypothesis": "",
                    "status": "error",
                    "error": str(e)
                })
        
        # 計算平均值
        avg_wer = total_wer / success_count if success_count > 0 else 0
        avg_cer = total_cer / success_count if success_count > 0 else 0
        avg_confidence = total_confidence / success_count if success_count > 0 else 0
        avg_word_accuracy = max(0, 100 - avg_wer)
        avg_char_accuracy = max(0, 100 - avg_cer)
        
        # 生成報告
        report = {
            "test_date": datetime.now().isoformat(),
            "total_cases": len(test_cases),
            "success_count": success_count,
            "failed_count": len(test_cases) - success_count,
            "success_rate": round(success_count / len(test_cases) * 100, 2) if test_cases else 0,
            "average_metrics": {
                "wer": round(avg_wer, 2),
                "cer": round(avg_cer, 2),
                "word_accuracy": round(avg_word_accuracy, 2),
                "char_accuracy": round(avg_char_accuracy, 2),
                "confidence": round(avg_confidence, 3)
            },
            "detailed_results": self.results
        }
        
        # 列印總結
        print("\n" + "="*70)
        print("📊 測試總結")
        print("="*70)
        print(f"總測試數: {report['total_cases']}")
        print(f"成功: {report['success_count']} | 失敗: {report['failed_count']}")
        print(f"成功率: {report['success_rate']}%")
        print(f"\n平均指標:")
        print(f"  - 平均 WER: {report['average_metrics']['wer']}%")
        print(f"  - 平均 CER: {report['average_metrics']['cer']}%")
        print(f"  - 平均詞準確率: {report['average_metrics']['word_accuracy']}%")
        print(f"  - 平均字準確率: {report['average_metrics']['char_accuracy']}%")
        print(f"  - 平均信心分數: {report['average_metrics']['confidence']}")
        print("="*70 + "\n")
        
        return report
    
    def save_report(self, report: Dict, output_path: str = None):
        """儲存測試報告"""
        if output_path is None:
            output_dir = "test_results/stt_evaluation"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(
                output_dir, 
                f"stt_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"✅ 測試報告已儲存: {output_path}")
        except Exception as e:
            logger.error(f"儲存報告失敗: {e}")


def main():
    """主程式"""
    # 設定路徑
    test_data_path = "test_data/stt_test/ground_truth.json"
    audio_dir = "test_data/stt_test/audio"
    
    # 建立測試器
    tester = STTBatchTester(test_data_path, audio_dir)
    
    # 執行測試
    report = tester.run_test()
    
    # 儲存報告
    if report:
        tester.save_report(report)


if __name__ == "__main__":
    main()
