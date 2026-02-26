# backend/services/stt_metrics.py
"""
STT 準確率評估工具
支援 WER (Word Error Rate) 和 CER (Character Error Rate) 計算
"""
import re
from typing import Tuple, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class STTMetrics:
    """STT 評估指標計算器"""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        標準化文字（移除標點符號、空格，統一大小寫）
        
        Args:
            text: 原始文字
            
        Returns:
            str: 標準化後的文字
        """
        # 移除標點符號
        text = re.sub(r'[，。！？、；：""''（）《》【】\s]', '', text)
        # 統一轉小寫（針對英文）
        text = text.lower()
        return text
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        計算 Levenshtein 距離（編輯距離）
        
        Args:
            s1: 字串1
            s2: 字串2
            
        Returns:
            int: 編輯距離
        """
        if len(s1) < len(s2):
            return STTMetrics.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # 插入、刪除、替換的成本
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @staticmethod
    def calculate_wer(reference: str, hypothesis: str) -> Tuple[float, Dict]:
        """
        計算 Word Error Rate (詞錯誤率)
        
        Args:
            reference: 正確文字（Ground Truth）
            hypothesis: STT 辨識結果
            
        Returns:
            Tuple[float, Dict]: (WER值, 詳細資訊)
        """
        # 標準化
        ref_normalized = STTMetrics.normalize_text(reference)
        hyp_normalized = STTMetrics.normalize_text(hypothesis)
        
        # 中文按字分詞，英文按空格分詞
        ref_words = list(ref_normalized) if any('\u4e00' <= c <= '\u9fff' for c in ref_normalized) else ref_normalized.split()
        hyp_words = list(hyp_normalized) if any('\u4e00' <= c <= '\u9fff' for c in hyp_normalized) else hyp_normalized.split()
        
        # 計算編輯距離
        distance = STTMetrics.levenshtein_distance(
            ''.join(ref_words), 
            ''.join(hyp_words)
        )
        
        # WER = 編輯距離 / 參考文字長度
        wer = distance / len(ref_words) if len(ref_words) > 0 else 0.0
        
        details = {
            "reference": reference,
            "hypothesis": hypothesis,
            "ref_length": len(ref_words),
            "hyp_length": len(hyp_words),
            "edit_distance": distance,
            "wer": round(wer * 100, 2)  # 轉換為百分比
        }
        
        return wer, details
    
    @staticmethod
    def calculate_cer(reference: str, hypothesis: str) -> Tuple[float, Dict]:
        """
        計算 Character Error Rate (字元錯誤率)
        
        Args:
            reference: 正確文字
            hypothesis: STT 辨識結果
            
        Returns:
            Tuple[float, Dict]: (CER值, 詳細資訊)
        """
        # 標準化
        ref_normalized = STTMetrics.normalize_text(reference)
        hyp_normalized = STTMetrics.normalize_text(hypothesis)
        
        # 計算編輯距離
        distance = STTMetrics.levenshtein_distance(ref_normalized, hyp_normalized)
        
        # CER = 編輯距離 / 參考文字長度
        cer = distance / len(ref_normalized) if len(ref_normalized) > 0 else 0.0
        
        details = {
            "reference": reference,
            "hypothesis": hypothesis,
            "ref_length": len(ref_normalized),
            "hyp_length": len(hyp_normalized),
            "edit_distance": distance,
            "cer": round(cer * 100, 2)  # 轉換為百分比
        }
        
        return cer, details
    
    @staticmethod
    def calculate_accuracy(reference: str, hypothesis: str) -> Dict:
        """
        計算綜合準確率指標
        
        Returns:
            Dict: 包含 WER, CER, Accuracy 的完整報告
        """
        wer, wer_details = STTMetrics.calculate_wer(reference, hypothesis)
        cer, cer_details = STTMetrics.calculate_cer(reference, hypothesis)
        
        # 準確率 = 1 - 錯誤率
        word_accuracy = max(0, 1 - wer) * 100
        char_accuracy = max(0, 1 - cer) * 100
        
        return {
            "wer": wer_details["wer"],
            "cer": cer_details["cer"],
            "word_accuracy": round(word_accuracy, 2),
            "char_accuracy": round(char_accuracy, 2),
            "reference": reference,
            "hypothesis": hypothesis,
            "edit_distance": wer_details["edit_distance"]
        }


# 測試範例
if __name__ == "__main__":
    # 測試案例
    test_cases = [
        {
            "reference": "我想應徵後端工程師的職位",
            "hypothesis": "我想應徵後端工程師的職位"
        },
        {
            "reference": "我有三年的 Python 開發經驗",
            "hypothesis": "我有三年的派森開發經驗"
        },
        {
            "reference": "下一題",
            "hypothesis": "下一天"
        }
    ]
    
    print("="*60)
    print("STT 準確率測試")
    print("="*60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n【測試 {i}】")
        result = STTMetrics.calculate_accuracy(
            case["reference"], 
            case["hypothesis"]
        )
        print(f"參考文字: {result['reference']}")
        print(f"辨識結果: {result['hypothesis']}")
        print(f"WER: {result['wer']}%")
        print(f"CER: {result['cer']}%")
        print(f"詞準確率: {result['word_accuracy']}%")
        print(f"字準確率: {result['char_accuracy']}%")
