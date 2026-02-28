"""
STT Evaluation Script - Azure Speech API + 本地 Common Voice 資料集
使用 pydub + ffmpeg 處理 mp3，送 Azure STT 評估
"""

import os
import gc
import csv
import time
import tempfile
import argparse
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pydub
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

DATASET_ROOT = r"common_voice_zh_TW\cv-corpus-24.0-2025-12-05\zh-TW"
CLIPS_DIR    = os.path.join(DATASET_ROOT, "clips")
TSV_PATH     = os.path.join(DATASET_ROOT, "test.tsv")

# ── 資料結構 ───────────────────────────────────────────────────────────────────
@dataclass
class EvalResult:
    sample_id:     int
    file_name:     str
    reference:     str
    hypothesis:    str
    cer:           float
    substitutions: int
    deletions:     int
    insertions:    int


# ── 文字預處理 ─────────────────────────────────────────────────────────────────
def normalize_text(text: str) -> str:
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


# ── MP3 轉 WAV ────────────────────────────────────────────────────────────────
def mp3_to_wav_tempfile(mp3_path: str) -> str:
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(tmp.name, format="wav")
    tmp.close()
    return tmp.name


# ── Azure STT ─────────────────────────────────────────────────────────────────
def transcribe_azure(mp3_path: str) -> str:
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION
    )
    speech_config.speech_recognition_language = "zh-TW"

    wav_path = mp3_to_wav_tempfile(mp3_path)
    text = ""

    audio_config = speechsdk.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        text = result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        text = ""
    else:
        print(f"  [錯誤] {result.reason}")
        text = ""

    # 釋放 SDK 資源後再刪暫存檔
    del recognizer
    del audio_config
    gc.collect()
    time.sleep(0.2)
    try:
        os.unlink(wav_path)
    except Exception:
        pass

    return text


# ── 讀取 TSV ───────────────────────────────────────────────────────────────────
def load_tsv(tsv_path: str, max_samples: int) -> List[dict]:
    rows = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
            if len(rows) >= max_samples:
                break
    return rows


# ── 主要評估流程 ───────────────────────────────────────────────────────────────
def evaluate(max_samples: int) -> List[EvalResult]:
    print(f"讀取 test.tsv，前 {max_samples} 筆...")
    rows = load_tsv(TSV_PATH, max_samples)
    print(f"共載入 {len(rows)} 筆，開始評估...\n")

    results = []

    for i, row in enumerate(rows):
        file_name = row["path"]
        reference = normalize_text(row["sentence"])
        mp3_path  = os.path.join(CLIPS_DIR, file_name)

        print(f"[{i+1}/{len(rows)}] {file_name}")
        print(f"  REF: {reference}")

        if not os.path.exists(mp3_path):
            print(f"  [跳過] 找不到音訊: {mp3_path}\n")
            continue

        hypothesis = normalize_text(transcribe_azure(mp3_path))
        print(f"  HYP: {hypothesis}")

        ref_tokens = tokenize(reference)
        hyp_tokens = tokenize(hypothesis)

        cer         = compute_cer(ref_tokens, hyp_tokens)
        sub, d, ins = compute_edit_ops(ref_tokens, hyp_tokens)

        print(f"  CER: {cer:.2%}  SUB:{sub} DEL:{d} INS:{ins}\n")

        results.append(EvalResult(
            sample_id=i+1,
            file_name=file_name,
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
        "file_name":     r.file_name,
        "reference":     r.reference,
        "hypothesis":    r.hypothesis,
        "cer":           round(r.cer, 4),
        "substitutions": r.substitutions,
        "deletions":     r.deletions,
        "insertions":    r.insertions,
    } for r in results]
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    print(f"✅ CSV 已儲存: {path}")


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
        f"Azure STT Evaluation — Common Voice 24.0 zh-TW\nOverall CER: {avg_cer:.2%}  (n={len(results)})",
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
    out = os.path.join(output_dir, "evaluation_results.png")
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
    print(f"  資料集      : Common Voice 24.0 zh-TW")
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
    parser = argparse.ArgumentParser(description="Azure STT CER Evaluation (Local Common Voice)")
    parser.add_argument("--samples",    type=int, default=100, help="評估筆數 (預設 100)")
    parser.add_argument("--output_csv", default="results.csv", help="CSV 輸出路徑")
    parser.add_argument("--output_dir", default="output",      help="圖表輸出資料夾")
    args = parser.parse_args()

    results = evaluate(args.samples)
    print_summary(results)
    save_csv(results, args.output_csv)
    plot_results(results, args.output_dir)


if __name__ == "__main__":
    main()