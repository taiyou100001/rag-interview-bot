# backend/api/stt_evaluation_router.py
"""
STT 評估與監控 API
提供 STT 服務品質監控與評估功能
"""
import os
import json
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from backend.services.enhanced_speech_service import enhanced_speech_service
from backend.services.stt_metrics import STTMetrics

router = APIRouter()


class STTEvaluationRequest(BaseModel):
    """STT 評估請求模型"""
    reference_text: str
    hypothesis_text: Optional[str] = None


class STTTestRequest(BaseModel):
    """STT 測試請求模型"""
    reference_text: str


@router.get("/stt/statistics", summary="取得 STT 服務統計資料")
async def get_stt_statistics():
    """
    取得 STT 服務的整體統計資料
    
    Returns:
        - total_requests: 總請求數
        - successful_requests: 成功請求數
        - failed_requests: 失敗請求數
        - success_rate: 成功率
        - avg_confidence: 平均信心分數
        - low_confidence_count: 低信心分數次數
    """
    try:
        stats = enhanced_speech_service.get_statistics()
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取得統計資料失敗: {str(e)}")


@router.post("/stt/evaluate", summary="評估 STT 準確率")
async def evaluate_stt_accuracy(req: STTEvaluationRequest):
    """
    評估 STT 辨識準確率
    
    提供參考文字和辨識結果，計算 WER、CER 等指標
    """
    try:
        if not req.hypothesis_text:
            return {
                "status": "error",
                "message": "需要提供辨識結果文字"
            }
        
        # 計算準確率指標
        metrics = STTMetrics.calculate_accuracy(
            req.reference_text,
            req.hypothesis_text
        )
        
        return {
            "status": "success",
            "data": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"評估失敗: {str(e)}")


@router.post("/stt/test_with_audio", summary="使用音檔測試 STT 準確率")
async def test_stt_with_audio(
    audio: UploadFile = File(..., description="測試音檔 (wav 格式)"),
    reference_text: str = Form(..., description="參考文字（正確答案）")
):
    """
    上傳音檔進行 STT 測試並評估準確率
    
    流程：
    1. 接收音檔
    2. 執行 STT 辨識
    3. 與參考文字比對
    4. 計算準確率指標
    """
    try:
        # 儲存暫存音檔
        temp_dir = "temp/stt_test"
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_filename = f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        with open(temp_path, "wb") as f:
            content = await audio.read()
            f.write(content)
        
        # 執行 STT
        stt_result = enhanced_speech_service.speech_to_text_with_confidence(temp_path)
        hypothesis = stt_result.get("text", "")
        confidence = stt_result.get("confidence", 0.0)
        quality = stt_result.get("quality", "unknown")
        
        # 計算準確率
        metrics = STTMetrics.calculate_accuracy(reference_text, hypothesis)
        
        # 清理暫存檔
        try:
            os.remove(temp_path)
        except:
            pass
        
        return {
            "status": "success",
            "stt_result": {
                "text": hypothesis,
                "confidence": confidence,
                "quality": quality
            },
            "evaluation": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"測試失敗: {str(e)}")


@router.get("/stt/recognition_logs", summary="取得 STT 辨識日誌")
async def get_recognition_logs(
    date: Optional[str] = None,
    limit: int = 100
):
    """
    取得 STT 辨識歷史日誌
    
    Args:
        date: 日期 (格式: YYYYMMDD)，不提供則使用今天
        limit: 返回筆數限制
    """
    try:
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        log_file = f"logs/stt_recognition/stt_log_{date}.jsonl"
        
        if not os.path.exists(log_file):
            return {
                "status": "success",
                "data": [],
                "message": f"日期 {date} 無辨識記錄"
            }
        
        logs = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    logs.append(log_entry)
                except:
                    continue
        
        # 限制返回筆數
        logs = logs[-limit:]
        
        # 統計分析
        total = len(logs)
        high_quality = sum(1 for log in logs if log.get('quality') == 'high')
        medium_quality = sum(1 for log in logs if log.get('quality') == 'medium')
        low_quality = sum(1 for log in logs if log.get('quality') == 'low')
        avg_conf = sum(log.get('confidence', 0) for log in logs) / total if total > 0 else 0
        
        return {
            "status": "success",
            "data": logs,
            "summary": {
                "total_records": total,
                "high_quality_count": high_quality,
                "medium_quality_count": medium_quality,
                "low_quality_count": low_quality,
                "average_confidence": round(avg_conf, 3)
            },
            "date": date
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取日誌失敗: {str(e)}")


@router.get("/stt/quality_report", summary="生成 STT 品質報告")
async def generate_quality_report(days: int = 7):
    """
    生成過去 N 天的 STT 品質報告
    
    Args:
        days: 統計天數（預設 7 天）
    """
    try:
        report_data = {
            "period": f"過去 {days} 天",
            "start_date": (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
            "end_date": datetime.now().strftime('%Y-%m-%d'),
            "daily_stats": []
        }
        
        total_requests = 0
        total_high_quality = 0
        total_medium_quality = 0
        total_low_quality = 0
        total_confidence = 0
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            log_file = f"logs/stt_recognition/stt_log_{date}.jsonl"
            
            if not os.path.exists(log_file):
                continue
            
            logs = []
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        logs.append(json.loads(line.strip()))
                    except:
                        continue
            
            if not logs:
                continue
            
            day_total = len(logs)
            day_high = sum(1 for log in logs if log.get('quality') == 'high')
            day_medium = sum(1 for log in logs if log.get('quality') == 'medium')
            day_low = sum(1 for log in logs if log.get('quality') == 'low')
            day_avg_conf = sum(log.get('confidence', 0) for log in logs) / day_total
            
            report_data["daily_stats"].append({
                "date": date,
                "total_requests": day_total,
                "high_quality": day_high,
                "medium_quality": day_medium,
                "low_quality": day_low,
                "average_confidence": round(day_avg_conf, 3)
            })
            
            total_requests += day_total
            total_high_quality += day_high
            total_medium_quality += day_medium
            total_low_quality += day_low
            total_confidence += day_avg_conf * day_total
        
        # 計算總體統計
        report_data["overall_stats"] = {
            "total_requests": total_requests,
            "high_quality_percentage": round(total_high_quality / total_requests * 100, 2) if total_requests > 0 else 0,
            "medium_quality_percentage": round(total_medium_quality / total_requests * 100, 2) if total_requests > 0 else 0,
            "low_quality_percentage": round(total_low_quality / total_requests * 100, 2) if total_requests > 0 else 0,
            "average_confidence": round(total_confidence / total_requests, 3) if total_requests > 0 else 0
        }
        
        return {
            "status": "success",
            "report": report_data,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成報告失敗: {str(e)}")
