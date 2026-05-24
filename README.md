# Japanese-Audio-Transcription-Translation-Pipeline
An automated, serverless pipeline that accepts a URL for any Japanese audio track, CD drama, or video, extracts the audio, transcribes it using OpenAI Whisper, and generates high-quality parallel translations (English/Chinese) using GPT-4o or Gemini 2.0.  Targeted Use Case: 动漫/游戏 CD 试听、访谈、语音包及古早广播剧

```bash
# Update package lists and install utilities + FFmpeg
ubuntu 24.4
sudo apt install python3-full
sudo apt install python3-pip
sudo apt install ffmpeg

# Verify FFmpeg installation
ffmpeg -version

# Ensure local pip binary paths are loaded in your terminal
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Install python libraries
pip3 install yt-dlp openai openai-whisper google-genai --break-system-packages

Whisper model (~1.5 GB) downloads automatically on first run.

### 2. Set your translation API key (pick one)

```bash
# GPT-4o (OpenAI) — paid, high quality
export OPENAI_API_KEY=sk-...

# Gemini (Google) — free tier available
export GEMINI_API_KEY=...
```

Get a Gemini key free at: https://aistudio.google.com/app/apikey
Get an OpenAI key at: https://platform.openai.com/api-keys

---

## Usage

```bash
# Japanese → Chinese via GPT-4o
python3 pipeline.py "https://..." --mode zh --translator gpt

# Japanese → English via Gemini
python3 pipeline.py "https://..." --mode en --translator gemini

# Japanese → Chinese + English
python3 pipeline.py "https://..." --mode both --translator gpt

# Japanese only, no translation
python3 pipeline.py "https://..." --mode none

# Custom output folder + larger Whisper model
python3 pipeline.py "https://..." --mode zh --translator gpt --out ./my_output --whisper-model large
```
---

## Examples
All processed batch files are generated into structural output directories. You can explore pre-rendered outputs inside the my_output/ folder of this repository:

JP to chinese+english:
python3 pipeline.py "https://www.bilibili.com/video/BV1Ct411f7nC/?spm_id_from=333.337.search-card.all.click&vd_source=93675b9f5fc7be8a722f7ff16cd66808" --mode both --out ./my_output
 python3 pipeline.py "https://www.bilibili.com/video/BV19tZPYpEzf/?spm_id_from=333.337.search-card.all.click&vd_source=93675b9f5fc7be8a722f7ff16cd66808" --mode both --out ./my_output

## Output

Two files are written to the output folder after every run:

### `<video title>.txt` — the transcript

```
https://www.youtube.com/watch?v=xxxx
Video Title Here
────────────────────────────────────────────────────────────

[00:12]
おはようございます。今日はよろしくお願いします。
早上好。今天请多关照。

[00:18]
こちらこそよろしくお願いします。
我才是，请多关照。
```

One Japanese paragraph, one translation paragraph, per segment.
Timestamps are from Whisper's natural sentence segmentation.

### `pipeline.log` — progress log

All processing messages go here instead of the terminal.
The only thing printed to the terminal is the output file path when done.

---

## Translation modes

| Mode | Japanese | Chinese | English |
|------|----------|---------|---------|
| `none` | ✓ | — | — |
| `zh`   | ✓ | ✓ | — |
| `en`   | ✓ | — | ✓ |
| `both` | ✓ | ✓ | ✓ |

---

## Whisper model sizes

| Model | Size | Speed | Japanese accuracy |
|-------|------|-------|-------------------|
| `tiny`   | 75 MB  | fastest | low |
| `base`   | 145 MB | fast    | ok |
| `small`  | 465 MB | medium  | good |
| `medium` | 1.5 GB | medium  | **best balance** (default) |
| `large`  | 3 GB   | slow    | highest |

---

## Cost

| Part | Cost |
|------|------|
| yt-dlp audio extraction | Free |
| Whisper transcription (local) | Free |
| GPT-4o translation | ~$0.01–0.10 per 30-min video |
| Gemini translation | Free tier: 60 requests/min |

Translation runs in parallel — all segments are sent at once,
so a 60-segment video takes ~20–30 seconds instead of several minutes.

##
