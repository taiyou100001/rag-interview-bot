"""
STT Evaluation Script - Azure Speech API + MagicData-RAMC
流程：讀 TXT 時間戳記 → 切割 WAV → Azure STT → 簡繁轉換 → 計算 CER
"""

import os
import gc
import csv
import re
import time
import tempfile
import argparse
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import wave
import struct
import opencc
import azure.cognitiveservices.speech as speechsdk
import editdistance
import matplotlib.pyplot as plt
import pandas as pd

# ── 設定 ──────────────────────────────────────────────────────────────────────
import sys

# 確保可以匯入 backend 模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings

# 現在你可以直接使用金鑰，而不必擔心外洩
AZURE_SPEECH_KEY = settings.AZURE_SPEECH_KEY
AZURE_SPEECH_REGION = settings.AZURE_SPEECH_REGION

# DATASET_ROOT = r"test_dataset"
# WAV_DIR      = os.path.join(DATASET_ROOT, "WAV")
# TXT_DIR      = os.path.join(DATASET_ROOT, "TXT")

# 獲取目前腳本所在的目錄 (即 scripts/ 資料夾)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 設定數據集路徑在 scripts/test_dataset
TEST_DATASET_DIR = os.path.join(SCRIPT_DIR, "test_dataset")
TXT_DIR = os.path.join(TEST_DATASET_DIR, "TXT")
WAV_DIR = os.path.join(TEST_DATASET_DIR, "WAV") # 如果有用到 WAV 資料夾的話

# 簡體 → 繁體轉換器
converter = opencc.OpenCC("s2twp")  # 簡體轉台灣繁體

# ── 資料結構 ───────────────────────────────────────────────────────────────────
@dataclass
class EvalResult:
    sample_id:     int
    file_id:       str
    start_time:    float
    end_time:      float
    reference:     str
    hypothesis:    str
    cer:           float
    substitutions: int
    deletions:     int
    insertions:    int


# ── 文字預處理 ─────────────────────────────────────────────────────────────────
def normalize_text(text: str) -> str:
    text = converter.convert(text)   # 簡→繁
    text = text.upper()
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if ch.isalnum() or ch == " ")
    return text.strip()


def tokenize(text: str) -> List[str]:
    tokens = []
    buf = ""
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
            if buf.strip():
                tokens.extend(buf.strip().split())
                buf = ""
            tokens.append(ch)
        else:
            buf += ch
    if buf.strip():
        tokens.extend(buf.strip().split())
    return [t for t in tokens if t]


# ── 錯誤分析 ───────────────────────────────────────────────────────────────────
def compute_edit_ops(ref: List[str], hyp: List[str]) -> Tuple[int, int, int]:
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = i
    for j in range(m + 1): dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i-1] == hyp[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j-1], dp[i-1][j], dp[i][j-1])
    sub = dele = ins = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i-1] == hyp[j-1]:
            i -= 1; j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
            sub += 1; i -= 1; j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
            dele += 1; i -= 1
        else:
            ins += 1; j -= 1
    return sub, dele, ins


def compute_cer(ref_tokens: List[str], hyp_tokens: List[str]) -> float:
    if not ref_tokens:
        return 0.0
    return editdistance.eval(ref_tokens, hyp_tokens) / len(ref_tokens)


# ── 讀取 TXT transcript ────────────────────────────────────────────────────────
NOISE_TAGS = {"[ENS]", "[NPS]", "[LAUGHTER]", "[SONANT]", "[MUSIC]", "[SYSTEM]", "[*]"}

def parse_txt(txt_path: str) -> List[dict]:
    """
    解析 TXT 格式:
    [start,end]  speaker_id  gender  transcript
    只保留有真實文字的行（跳過噪音標記）
    """
    entries = []
    pattern = re.compile(r'\[(\d+\.\d+),(\d+\.\d+)\]\s+(\S+)\s+(\S+)\s+(.*)')

    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = pattern.match(line)
            if not m:
                continue
            start, end, speaker, gender, transcript = m.groups()
            transcript = transcript.strip()

            # 跳過純噪音行
            if transcript in NOISE_TAGS or not transcript:
                continue
            # 跳過含 [*] 的行（無法辨識）
            if "[*]" in transcript:
                continue
            # 移除行內噪音標記但保留文字
            for tag in NOISE_TAGS:
                transcript = transcript.replace(tag, "").strip()
            if not transcript:
                continue

            entries.append({
                "start": float(start),
                "end":   float(end),
                "transcript": transcript
            })

    return entries


# ── 切割 WAV ───────────────────────────────────────────────────────────────────
def slice_wav(wav_path: str, start: float, end: float) -> str:
    """
    從長 WAV 切出指定時間段，存成暫存 WAV 檔，回傳路徑
    """
    with wave.open(wav_path, "rb") as wf:
        framerate   = wf.getframerate()
        n_channels  = wf.getnchannels()
        sampwidth   = wf.getsampwidth()

        start_frame = int(start * framerate)
        end_frame   = int(end * framerate)
        n_frames    = end_frame - start_frame

        wf.setpos(start_frame)
        frames = wf.readframes(n_frames)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as out:
        out.setnchannels(n_channels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)
        out.writeframes(frames)
    tmp.close()
    return tmp.name


# ── Azure STT ─────────────────────────────────────────────────────────────────
def transcribe_azure(wav_path: str) -> str:
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION
    )
    speech_config.speech_recognition_language = "zh-TW"

    audio_config = speechsdk.AudioConfig(filename=wav_path)
    recognizer   = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    result = recognizer.recognize_once()

    text = ""
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        text = result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        text = ""
    else:
        print(f"    [錯誤] {result.reason}")
        text = ""

    del recognizer
    del audio_config
    gc.collect()
    time.sleep(0.2)

    return text


# ── 主要評估流程 ───────────────────────────────────────────────────────────────
def evaluate(max_samples: int, per_file: int = 10) -> List[EvalResult]:
    txt_files = sorted([f for f in os.listdir(TXT_DIR) if f.endswith(".txt")])
    results   = []
    sample_id = 0

    for txt_file in txt_files:
        if sample_id >= max_samples:
            break

        base     = os.path.splitext(txt_file)[0]
        txt_path = os.path.join(TXT_DIR, txt_file)
        wav_path = os.path.join(WAV_DIR, base + ".wav")

        if not os.path.exists(wav_path):
            print(f"[跳過] 找不到 WAV: {wav_path}")
            continue

        print(f"\n📂 {base}")
        entries = parse_txt(txt_path)

        # 每個檔案等距抽樣
        if per_file > 0 and len(entries) > per_file:
            step = max(1, len(entries) // per_file)
            entries = entries[::step][:per_file]

        file_count = 0
        for entry in entries:
            if sample_id >= max_samples:
                break

            sample_id += 1
            file_count += 1
            start     = entry["start"]
            end       = entry["end"]
            reference = normalize_text(entry["transcript"])

            if not reference:
                continue

            print(f"  [{sample_id}/{max_samples}] {start:.2f}s~{end:.2f}s")
            print(f"    REF: {reference}")

            tmp_wav   = slice_wav(wav_path, start, end)
            hypothesis = normalize_text(transcribe_azure(tmp_wav))

            try:
                os.unlink(tmp_wav)
            except Exception:
                pass

            print(f"    HYP: {hypothesis}")

            ref_tokens = tokenize(reference)
            hyp_tokens = tokenize(hypothesis)

            cer         = compute_cer(ref_tokens, hyp_tokens)
            sub, d, ins = compute_edit_ops(ref_tokens, hyp_tokens)

            print(f"    CER: {cer:.2%}  SUB:{sub} DEL:{d} INS:{ins}")

            results.append(EvalResult(
                sample_id=sample_id,
                file_id=base,
                start_time=start,
                end_time=end,
                reference=reference,
                hypothesis=hypothesis,
                cer=cer,
                substitutions=sub,
                deletions=d,
                insertions=ins
            ))

            time.sleep(0.1)

    return results


# ── 輸出 CSV ───────────────────────────────────────────────────────────────────
def save_csv(results: List[EvalResult], path: str):
    rows = [{
        "sample_id":     r.sample_id,
        "file_id":       r.file_id,
        "start_time":    r.start_time,
        "end_time":      r.end_time,
        "reference":     r.reference,
        "hypothesis":    r.hypothesis,
        "cer":           round(r.cer, 4),
        "substitutions": r.substitutions,
        "deletions":     r.deletions,
        "insertions":    r.insertions,
    } for r in results]
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n✅ CSV 已儲存: {path}")


# ── 視覺化 ─────────────────────────────────────────────────────────────────────
def plot_results(results: List[EvalResult], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    cers      = [r.cer for r in results]
    avg_cer   = np.mean(cers)
    total_sub = sum(r.substitutions for r in results)
    total_del = sum(r.deletions for r in results)
    total_ins = sum(r.insertions for r in results)
    total_err = total_sub + total_del + total_ins

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        f"Azure STT Evaluation — MagicData-RAMC (簡→繁)\nOverall CER: {avg_cer:.2%}  (n={len(results)})",
        fontsize=13, fontweight="bold"
    )

    ax = axes[0]
    ax.bar(range(len(cers)), cers, color="#4A90D9", alpha=0.85, edgecolor="white")
    ax.axhline(avg_cer, color="#E74C3C", linestyle="--", linewidth=1.5, label=f"Avg {avg_cer:.2%}")
    ax.set_title("CER per Sample")
    ax.set_xlabel("Sample Index")
    ax.set_ylabel("CER")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.legend(); ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    if total_err > 0:
        sizes  = [total_sub, total_del, total_ins]
        labels = [f"Sub\n({total_sub})", f"Del\n({total_del})", f"Ins\n({total_ins})"]
        colors = ["#E74C3C", "#F39C12", "#2ECC71"]
        ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%",
               startangle=140, wedgeprops=dict(edgecolor="white", linewidth=2))
    ax.set_title("Error Type Distribution")

    ax = axes[2]
    ax.hist(cers, bins=10, color="#9B59B6", alpha=0.85, edgecolor="white")
    ax.axvline(avg_cer, color="#E74C3C", linestyle="--", linewidth=1.5, label=f"Mean {avg_cer:.2%}")
    ax.set_title("CER Distribution")
    ax.set_xlabel("CER")
    ax.set_ylabel("Count")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.legend(); ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    out = os.path.join(output_dir, "magicdata_results.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ 圖表已儲存: {out}")


# ── 摘要 ───────────────────────────────────────────────────────────────────────
def print_summary(results: List[EvalResult]):
    if not results: return
    cers      = [r.cer for r in results]
    total_sub = sum(r.substitutions for r in results)
    total_del = sum(r.deletions for r in results)
    total_ins = sum(r.insertions for r in results)
    total_err = total_sub + total_del + total_ins

    print("\n" + "="*50)
    print("        📊 評估摘要報告")
    print("="*50)
    print(f"  資料集      : MagicData-RAMC (簡→繁轉換)")
    print(f"  總樣本數    : {len(results)}")
    print(f"  Average CER : {np.mean(cers):.2%}")
    print(f"  Median CER  : {np.median(cers):.2%}")
    print(f"  Min CER     : {min(cers):.2%}")
    print(f"  Max CER     : {max(cers):.2%}")
    print("-"*50)
    if total_err:
        print(f"  Substitution: {total_sub} ({total_sub/total_err:.1%})")
        print(f"  Deletion    : {total_del} ({total_del/total_err:.1%})")
        print(f"  Insertion   : {total_ins} ({total_ins/total_err:.1%})")
    print("="*50)


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Azure STT CER Evaluation (MagicData-RAMC)")
    parser.add_argument("--samples",    type=int, default=100, help="評估筆數 (預設 100)")
    parser.add_argument("--output_csv", default="magicdata_results.csv", help="CSV 輸出路徑")
    parser.add_argument("--output_dir", default="output", help="圖表輸出資料夾")
    parser.add_argument("--per_file",   type=int, default=10, help="每個音檔抽幾筆 (預設 10)")
    args = parser.parse_args()

    results = evaluate(args.samples, args.per_file)
    print_summary(results)
    save_csv(results, args.output_csv)
    plot_results(results, args.output_dir)


if __name__ == "__main__":
    main()