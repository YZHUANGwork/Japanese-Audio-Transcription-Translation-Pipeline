"""
Audio Pipeline
──────────────
URL → extract audio → Whisper transcription → parallel GPT/Gemini translation → txt file

No server. No speaker diarization. No terminal output — all progress goes to pipeline.log.
The only thing printed to terminal is the final output file path.

Requirements:
  pip install yt-dlp openai-whisper
  pip install openai        # for GPT-4o
  pip install google-genai  # for Gemini
  brew install ffmpeg       # macOS
  apt  install ffmpeg       # Linux

Environment variables:
  OPENAI_API_KEY  — required if using --translator gpt
  GEMINI_API_KEY  — required if using --translator gemini

Usage:
  python pipeline.py "https://..." --mode zh --translator gpt
  python pipeline.py "https://..." --mode both --translator gemini
  python pipeline.py "https://..." --mode none
  python pipeline.py "https://..." --mode zh --out ./my_output --whisper-model large

Output files (written to --out folder):
  <video title>.txt   — transcript: one Japanese paragraph, one translation paragraph
  pipeline.log        — progress log (no terminal spam)
"""

import os
import sys
import tempfile
import subprocess
import concurrent.futures
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Optional

# ── Dependency checks ────────────────────────────────────────────────────────
try:
    import yt_dlp
except ImportError:
    sys.exit("Missing: pip install yt-dlp")

try:
    import whisper as local_whisper
except ImportError:
    sys.exit("Missing: pip install openai-whisper")


# ── Config ───────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
WHISPER_MODEL  = "medium"   # tiny / base / small / medium / large

TranslationMode   = Literal["none", "zh", "en", "both"]
TranslatorBackend = Literal["gpt", "gemini"]

_whisper_model = None


# ── Data ─────────────────────────────────────────────────────────────────────
@dataclass
class Segment:
    start:    float
    end:      float
    japanese: str
    chinese:  Optional[str] = None
    english:  Optional[str] = None


# ── Whisper (loaded once, reused) ─────────────────────────────────────────────
def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = local_whisper.load_model(WHISPER_MODEL)
    return _whisper_model


# ── Translation ───────────────────────────────────────────────────────────────
SYSTEM_PROMPTS = {
    "zh": (
        "你是专业的日中翻译员。将用户发送的日语翻译成简体中文。"
        "保持原文语气和风格。只输出翻译结果，不要解释或加注释。"
    ),
    "en": (
        "You are a professional Japanese-to-English translator. "
        "Translate the Japanese the user sends into natural, fluent English. "
        "Preserve tone and style. Output only the translation, no explanations."
    ),
}


def translate_gpt(text: str, lang: str) -> str:
    try:
        import openai
    except ImportError:
        sys.exit("Missing: pip install openai")
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPTS[lang]},
            {"role": "user",   "content": text},
        ],
    )
    return resp.choices[0].message.content.strip()


def translate_gemini(text: str, lang: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        sys.exit("Missing: pip install google-genai")
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = SYSTEM_PROMPTS[lang] + "\n\n" + text
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return resp.text.strip()


def translate_one(text: str, lang: str, backend: TranslatorBackend) -> str:
    """Translate a single segment. Called in parallel threads."""
    if not text.strip():
        return ""
    if backend == "gpt":
        return translate_gpt(text, lang)
    return translate_gemini(text, lang)


def translate_parallel(segments: list, lang: str,
                        backend: TranslatorBackend, log) -> list:
    """
    Send all segment translations at once via a thread pool.
    Returns list of translated strings in original order.
    """
    log(f"  translating {len(segments)} segments to {'zh' if lang == 'zh' else 'en'} [{backend}] in parallel...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(translate_one, seg.japanese, lang, backend): i
            for i, seg in enumerate(segments)
        }
        results = [""] * len(segments)
        done = 0
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            done += 1
            try:
                results[i] = future.result()
            except Exception as e:
                results[i] = f"[error: {e}]"
                log(f"  WARNING: segment {i+1} failed: {e}")
            log(f"  {done}/{len(segments)} done")

    return results


# ── Step 1: Extract audio ─────────────────────────────────────────────────────
def extract_audio(url: str, output_dir: str, log) -> tuple:
    log("[1/4] Extracting audio...")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "audio.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        
        # ── THE ONLY TWO LINES YOU ACTUALLY NEED ─────────────────────────────
        "retries": 10,  # Automatically retry if Bilibili drops the connection
        "http_headers": {"Referer": "https://www.bilibili.com/"},  # Stop Bilibili from blocking the bot
    }
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "audio.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
    }
    """
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info  = ydl.extract_info(url, download=True)
        title = info.get("title", "Unknown")

    candidates = sorted(Path(output_dir).glob("audio.*"))
    if not candidates:
        raise FileNotFoundError("Audio extraction failed — no output file found.")
    log(f"  audio: {candidates[0].name} | title: {title}")
    return str(candidates[0]), title


# ── Step 2: Transcribe with Whisper ──────────────────────────────────────────
def transcribe(audio_path: str, log) -> list:
    """
    Run local Whisper on the whole audio file.
    Whisper segments naturally at sentence/pause boundaries.
    """
    log(f"[2/4] Transcribing with Whisper ({WHISPER_MODEL}) — may take several minutes...")
    model  = get_whisper()
    result = model.transcribe(audio_path, language="ja", fp16=False, verbose=False)

    segments = []
    for seg in result.get("segments", []):
        text = seg["text"].strip()
        if text:
            segments.append(Segment(
                start    = round(seg["start"], 2),
                end      = round(seg["end"],   2),
                japanese = text,
            ))

    log(f"  {len(segments)} segments transcribed")
    return segments


# ── Step 3: Translate in parallel ─────────────────────────────────────────────
def translate_segments(segments: list, mode: TranslationMode,
                        backend: TranslatorBackend, log) -> list:
    """Translate all segments for each requested language, in parallel."""
    if mode == "none" or not segments:
        return segments

    log("[3/4] Translating...")

    if mode in ("zh", "both"):
        translations = translate_parallel(segments, "zh", backend, log)
        for seg, zh in zip(segments, translations):
            seg.chinese = zh

    if mode in ("en", "both"):
        translations = translate_parallel(segments, "en", backend, log)
        for seg, en in zip(segments, translations):
            seg.english = en

    return segments


# ── Step 4: Write output txt ──────────────────────────────────────────────────
def write_txt(segments: list, title: str, url: str, mode: TranslationMode,
              out_path: str, log):
    """
    Output format (mode=zh example):

      Video Title
      ────────────────────────────────────────────────────────────

      [00:12]
      おはようございます。今日はよろしくお願いします。
      早上好。今天请多关照。

      [00:18]
      こちらこそよろしくお願いします。
      我才是，请多关照。
    """
    log(f"[4/4] Writing {out_path}...")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(url + "\n")
        f.write(title + "\n")
        f.write("─" * 60 + "\n\n")

        for seg in segments:
            f.write(f"[{fmt(seg.start)}]\n")
            f.write(seg.japanese + "\n")
            if mode in ("zh", "both") and seg.chinese:
                f.write(seg.chinese + "\n")
            if mode in ("en", "both") and seg.english:
                f.write(seg.english + "\n")
            f.write("\n")

    log(f"  written: {out_path}")


def fmt(sec: float) -> str:
    s = int(sec)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ── Full pipeline ─────────────────────────────────────────────────────────────
def run_pipeline(
    url:        str,
    mode:       TranslationMode   = "zh",
    translator: TranslatorBackend = "gpt",
    out_dir:    str               = "./output",
) -> str:
    """
    Run the full pipeline. Returns path to the output txt file.
    All progress is written to <out_dir>/pipeline.log — nothing printed to terminal.
    """
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "pipeline.log")

    def log(msg: str):
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(msg + "\n")

    log(f"url:        {url}")
    log(f"mode:       {mode}")
    log(f"translator: {translator if mode != 'none' else 'n/a'}")
    log(f"whisper:    {WHISPER_MODEL}")
    # ── Sweep and destroy old leftover folders from past runs ────
    for p in Path(out_dir).glob("tmp*"):
        if p.is_dir():
            for f in p.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                p.rmdir()
            except Exception:
                pass
    # ─────────────────────────────────────────────────────────────────────────



    tmp = tempfile.mkdtemp(dir=out_dir)
    try:
        audio_path, title = extract_audio(url, tmp, log)
        segments          = transcribe(audio_path, log)
        segments          = translate_segments(segments, mode, translator, log)

        safe     = "".join(c if c.isalnum() or c in " -_()" else "_" for c in title)[:60].strip()
        out_path = os.path.join(out_dir, safe + ".txt")
        
        # Fixed signature
        write_txt(segments, title, url, mode, out_path, log)
        log("done.")
        
    finally:
        # ── GUARANTEED CLEANUP ───────────────────────────────────────────────
        # This block ALWAYS runs, even if write_txt or Whisper crashes!
        log(f"Cleaning up temporary folder: {tmp}")
        for f in Path(tmp).glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            Path(tmp).rmdir()
        except Exception:
            pass
        # ─────────────────────────────────────────────────────────────────────

    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="URL → Whisper → GPT/Gemini translation → txt file"
    )
    parser.add_argument("url",
        help="URL of any page with audio or video")
    parser.add_argument("--mode", default="zh",
        choices=["none", "zh", "en", "both"],
        help="Translation output: none | zh | en | both  (default: zh)")
    parser.add_argument("--translator", default="gpt",
        choices=["gpt", "gemini"],
        help="gpt (OpenAI GPT-4o) or gemini (Google Gemini)  (default: gpt)")
    parser.add_argument("--out", default="./output",
        help="Output folder  (default: ./output)")
    parser.add_argument("--whisper-model", default="medium",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size  (default: medium)")
    args = parser.parse_args()

    if args.mode != "none":
        if args.translator == "gpt" and not OPENAI_API_KEY:
            sys.exit("Error: OPENAI_API_KEY not set.  export OPENAI_API_KEY=sk-...")
        if args.translator == "gemini" and not GEMINI_API_KEY:
            sys.exit("Error: GEMINI_API_KEY not set.  export GEMINI_API_KEY=...")

    WHISPER_MODEL = args.whisper_model

    out_path = run_pipeline(
        url        = args.url,
        mode       = args.mode,
        translator = args.translator,
        out_dir    = args.out,
    )

    # Only one line ever printed to terminal — the output file path
    print(out_path)
