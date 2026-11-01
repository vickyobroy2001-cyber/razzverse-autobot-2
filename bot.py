import os
import re
import sys
import json
import time
import random
import shutil
import asyncio
import logging
import subprocess
import traceback
import urllib.parse
from io import BytesIO
from contextlib import contextmanager
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image


# ---- config -----------------------------------------------------------------
def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


W, H = 1080, 1920                                  # final video size
GEN_W, GEN_H = _env_int("IMG_GEN_W", 720), _env_int("IMG_GEN_H", 1280)  # generate small = faster; use 1080x1920 for sharper
FPS = 24
IMG_WORKERS = max(1, _env_int("IMG_WORKERS", 3))
SEND_FILE_TO_WEBHOOK = os.environ.get("WEBHOOK_SEND_FILE", "1") != "0"   # set to 0 to send only the link (faster)
# Better: put the URL in the MAKE_WEBHOOK_URL secret and delete this default.
DEFAULT_WEBHOOK = "https://hook.us2.make.com/dvt7x9d1fceu5vbr43snt0w8tyysw0dg"

VOICE = os.environ.get("TTS_VOICE", "hi-IN-SwaraNeural")
OUT_VIDEO, OUT_AUDIO, OUT_META = "razzverse_short.mp4", "voice.mp3", "metadata.json"
UA = {"User-Agent": "Mozilla/5.0"}
PREFERRED_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
SKIP_MODEL_WORDS = ("image", "tts", "live", "embedding", "veo", "imagen", "aqa",
                    "robotics", "computer", "audio", "gemma", "learnlm", "vision")

NICHES = [
    "Psychology & Mind Tricks (दिमाग और व्यवहार के गहरे रहस्य)",
    "Dark History & Untold Secrets (इतिहास के रहस्यमयी और अनसुने पन्ने)",
    "Bizarre Facts & Mystery (दुनिया के अजीबोगरीब और चौंकाने वाले तथ्य)",
    "Success, Money & Power Laws (सफलता, पैसा और शक्ति के मनोवैज्ञानिक नियम)",
]

# Used only if Gemini is totally unavailable, so the channel still posts. One per niche.
FALLBACKS = [
    {
        "title": "Eye Contact Ka Secret Trick #shorts #razzverse",
        "caption": "Ye psychology trick try karke bataiye! #razzverse #hindishorts #psychology #mindtricks #shorts",
        "theme": "two people talking, intense eye contact, psychology concept",
        "voiceover": "क्या आपको पता है? जब आप किसी की आँखों में देखकर बात करते हो, तो सामने वाला आप पर ज़्यादा भरोसा करता है! साइकोलॉजी कहती है कि तीन सेकंड का आई कॉन्टैक्ट आपको कॉन्फिडेंट दिखाता है। अगली बार किसी से बात करो तो ये ट्रिक ज़रूर आज़माना। और हाँ, ऐसे ही मज़ेदार फैक्ट्स के लिए रज़्ज़वर्स को फॉलो करना मत भूलना!",
    },
    {
        "title": "Jab Poora Shehar Nachne Laga #shorts #razzverse",
        "caption": "Itihaas ka ajeeb sach! #razzverse #hindishorts #history #mystery #shorts",
        "theme": "medieval European town square 1518, crowd dancing in a trance, dark eerie",
        "voiceover": "क्या आप जानते हो कि 1518 में आज के फ्रांस के स्ट्रासबर्ग शहर में लोग अचानक नाचने लगे, और रुके ही नहीं? इसे डांसिंग प्लेग कहा जाता है! रिकॉर्ड्स के मुताबिक सैकड़ों लोग कई दिनों तक नाचते रहे, और कहा जाता है कि कुछ की थकान से जान भी चली गई। आज भी वैज्ञानिक इसकी असली वजह पर बहस करते हैं। ऐसे और रहस्यों के लिए रज़्ज़वर्स को फॉलो करो!",
    },
    {
        "title": "Shahad Kabhi Kharab Kyun Nahi Hota? #shorts #razzverse",
        "caption": "Science ka kamaal! #razzverse #hindishorts #facts #mystery #shorts",
        "theme": "golden honey dripping, ancient Egyptian tomb, macro photography",
        "voiceover": "क्या आप जानते हो कि शहद कभी खराब नहीं होता? वैज्ञानिकों को मिस्र के मकबरों में हज़ारों साल पुराना शहद मिला, जो आज भी खाने लायक था! इसकी वजह है शहद में बहुत कम पानी और नेचुरल एंटीबैक्टीरियल गुण। है ना कमाल की साइंस? और भी ऐसे रहस्यों के लिए रज़्ज़वर्स को फॉलो करो!",
    },
    {
        "title": "80/20 Ka Secret Rule #shorts #razzverse",
        "caption": "Pareto rule samjho! #razzverse #hindishorts #success #money #shorts",
        "theme": "businessman at a glowing chessboard, golden coins, power and success concept",
        "voiceover": "क्या आप जानते हो कि आपके 80 प्रतिशत नतीजे सिर्फ़ 20 प्रतिशत कामों से आते हैं? इसे पैरेटो रूल कहते हैं। इटली के इकोनॉमिस्ट विल्फ्रेडो पैरेटो ने देखा था कि वहाँ की ज़्यादातर ज़मीन बहुत थोड़े से लोगों के पास थी। आज भी ये नियम पैसे, बिज़नेस और टाइम पर लागू होता है। अपने वो बीस प्रतिशत काम ढूँढो जो असली नतीजे देते हैं! ऐसे और नियमों के लिए रज़्ज़वर्स को फॉलो करो!",
    },
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("razzverse")


# ---- helpers ----------------------------------------------------------------
@contextmanager
def stage(name):
    t = time.time()
    log.info(">> %s", name)
    try:
        yield
    finally:
        log.info("<< %s finished in %.1fs", name, time.time() - t)


def retry(fn, tries=3, delay=2, what="task"):
    last = None
    for i in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning("%s failed (%d/%d): %s", what, i, tries, str(e)[:200])
            if i < tries:
                time.sleep(delay * i)
    raise last


def themed_prompts(theme):
    angles = ["wide establishing shot", "close-up detail", "dramatic low angle",
              "moody atmospheric lighting", "glowing abstract concept art"]
    return [f"cinematic vertical 9:16 dark moody 8k, {theme}, {a}, volumetric light, ultra detailed, no text"
            for a in angles]


def clean_voice(text):
    text = re.sub(r"#\w+", "", text)                                   # hashtags
    text = re.sub(r"[*_`~<>\[\]{}|]", "", text)                        # markdown junk
    text = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27BF]", "", text)   # emojis
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    if len(words) > 200:                                               # keep the Short short
        text = " ".join(words[:200])
        cut = max(text.rfind("।"), text.rfind("."), text.rfind("?"), text.rfind("!"))
        if cut > len(text) * 0.6:
            text = text[: cut + 1]
    return text


def extract_json(text):
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    candidates = [t]
    if "{" in t and "}" in t:
        candidates.append(t[t.find("{"): t.rfind("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, list) and obj:
                obj = obj[0]
            if isinstance(obj, dict):
                return obj
        except Exception:  # noqa: BLE001
            continue
    return None


def normalize(d, idx):
    """Validate/repair the script dict (accepts 'voiceover' or 'script'). None if unusable."""
    if not isinstance(d, dict):
        return None
    voice = clean_voice(str(d.get("voiceover") or d.get("script") or ""))
    if len(voice.split()) < 15:
        return None

    title = str(d.get("title") or "").strip()[:80].rstrip() or FALLBACKS[idx]["title"][:80]
    if "#shorts" not in title.lower():
        title += " #shorts"
    title = title[:100]

    caption = str(d.get("caption") or "").strip() or FALLBACKS[idx]["caption"]
    if "#razzverse" not in caption.lower():
        caption += " #razzverse"

    raw_prompts = d.get("image_prompts") or []
    if isinstance(raw_prompts, str):
        raw_prompts = [raw_prompts]
    prompts = [str(p).strip()[:400] for p in raw_prompts if str(p).strip()]
    if not prompts:
        prompts = themed_prompts(FALLBACKS[idx]["theme"])
    i = 0
    while len(prompts) < 5:
        prompts.append(prompts[i % len(prompts)])
        i += 1
    return {"title": title, "caption": caption, "voiceover": voice, "image_prompts": prompts[:6]}


def fallback_script(idx):
    fb = dict(FALLBACKS[idx])
    fb["image_prompts"] = themed_prompts(fb["theme"])
    return normalize(fb, idx)


# ---- stage 1: script (Gemini) -----------------------------------------------
def build_prompt(niche):
    return f"""You are the viral creator for 'Razzverse'. Write a 45-second YouTube Short / IG Reel in the niche: {niche}.
Start with a 3-second shocking hook. Keep pacing fast, suspenseful, and end with a mind-blowing twist or question.
Write the 'voiceover' in natural, conversational spoken Hindi (Devanagari script) mixed with common English words (written in Devanagari, e.g., साइकोलॉजी, ट्रिक, AI, रिसर्च) so the Hindi TTS pronounces it natively. Around 100 words.
No emojis, hashtags, asterisks or stage directions inside the voiceover. Only state facts that are true.
Return ONLY valid JSON with these exact keys:
{{"title": "Catchy Hinglish Title under 60 chars #shorts #razzverse", "voiceover": "Spoken Hindi script in Devanagari...", "caption": "Engaging Hindi/Hinglish caption with 5 hashtags #razzverse #hindishorts", "image_prompts": ["cinematic vertical 9:16 dark moody detailed prompt 1", "prompt 2", "prompt 3", "prompt 4", "prompt 5"]}}"""


def get_client():
    raw = os.environ.get("GEMINI_API_KEY", "")
    m = re.search(r"AIza[0-9A-Za-z\-_]{35}", raw)
    key = m.group(0) if m else raw.strip()
    if not key:
        log.warning("GEMINI_API_KEY is empty - will use fallback script")
        return None
    try:
        from google import genai
        try:
            return genai.Client(api_key=key, http_options={"timeout": 60_000})   # never hang forever
        except Exception:  # noqa: BLE001
            return genai.Client(api_key=key)
    except Exception as e:  # noqa: BLE001
        log.warning("Gemini client unavailable: %s", e)
        return None


def gen_config(model, thinking_off):
    cfg = {"response_mime_type": "application/json", "temperature": 1.0}
    if thinking_off and "2.5-flash" in model and "lite" not in model:
        cfg["thinking_config"] = {"thinking_budget": 0}     # much faster, plenty good for a 100-word script
    return cfg


def try_models(client, models, prompt, idx):
    """Returns (data, fatal). fatal=True means the key itself is bad."""
    for model in models:
        thinking_off = True
        for attempt in range(1, 3):
            try:
                log.info("Trying %s (attempt %d)...", model, attempt)
                res = client.models.generate_content(model=model, contents=prompt,
                                                     config=gen_config(model, thinking_off))
                data = normalize(extract_json(res.text), idx)
                if data:
                    return data, False
                log.warning("%s returned unusable JSON", model)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                log.warning("Skip %s: %s", model, msg[:200])
                low = msg.lower()
                if "thinking" in low and thinking_off:
                    thinking_off = False                   # model doesn't support it: retry plain
                    continue
                if any(x in msg for x in ("API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED")):
                    return None, True
                if "404" in msg or "NOT_FOUND" in msg or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    break                                  # retired or out of quota: next model
                time.sleep(2 * attempt)                    # 503 / overloaded: short backoff
    return None, False


def discover_models(client, already):
    found = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if ("gemini" in name and name not in already and name not in found
                    and not any(w in name for w in SKIP_MODEL_WORDS)
                    and (not actions or "generateContent" in actions)):
                found.append(name)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not list models: %s", e)
    found.sort(reverse=True)                       # newer versions first
    found.sort(key=lambda n: "flash" not in n)     # flash models first
    return found[:5]


def get_script(client, idx):
    if client is None:
        return None
    prompt = build_prompt(NICHES[idx])
    models = []
    if os.environ.get("GEMINI_MODEL"):
        models.append(os.environ["GEMINI_MODEL"].strip())
    models += [m for m in PREFERRED_MODELS if m not in models]
    data, fatal = try_models(client, models, prompt, idx)     # fast path: no model listing
    if data or fatal:
        return data
    extra = discover_models(client, models)                   # only if the usual ones all failed
    if extra:
        data, _ = try_models(client, extra, prompt, idx)
    return data


# ---- stage 2: voice ---------------------------------------------------------
async def _edge_save(text, out, **prosody):
    import edge_tts
    await edge_tts.Communicate(text=text, voice=VOICE, **prosody).save(out)


def _file_ok(path, min_size=1000):
    return os.path.exists(path) and os.path.getsize(path) > min_size


def make_voice(text, out=OUT_AUDIO):
    for prosody in ({"rate": "+10%", "pitch": "-2Hz"}, {"rate": "+10%"}, {}):
        def attempt(p=prosody):
            if os.path.exists(out):
                os.remove(out)
            with ThreadPoolExecutor(1) as ex:       # safe even if an event loop is already running
                ex.submit(asyncio.run, _edge_save(text, out, **p)).result()
            if not _file_ok(out):
                raise RuntimeError("edge-tts produced empty audio")
        try:
            retry(attempt, tries=2, delay=2, what=f"edge-tts {prosody}")
            return out
        except Exception:  # noqa: BLE001
            continue

    log.warning("edge-tts failed - trying gTTS fallback")
    try:
        from gtts import gTTS
        retry(lambda: gTTS(text=text, lang="hi").save(out), tries=3, delay=2, what="gTTS")
        if _file_ok(out):
            return out
    except Exception as e:  # noqa: BLE001
        log.error("gTTS fallback failed: %s", e)
    raise RuntimeError("No audio could be generated")


# ---- stage 3: images (parallel) ---------------------------------------------
def fit_and_save(img, path):
    """Cover-crop any image to exactly 1080x1920."""
    img = img.convert("RGB")
    scale = max(W / img.width, H / img.height)
    nw, nh = int(img.width * scale) + 1, int(img.height * scale) + 1
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    img.crop((left, top, left + W, top + H)).save(path, "JPEG", quality=90)


def make_gradient(idx, path):
    top = [(32, 20, 70), (70, 20, 60), (15, 50, 80), (60, 40, 20), (20, 60, 50)][idx % 5]
    bot = (8, 8, 20)
    col = Image.new("RGB", (1, H))
    col.putdata([tuple(int(top[c] + (bot[c] - top[c]) * y / H) for c in range(3)) for y in range(H)])
    col.resize((W, H)).save(path, "JPEG", quality=90)
    return path


def get_image(idx, prompt):
    path = f"scene_{idx}.jpg"
    base_seed = int(time.time()) + idx
    time.sleep(0.4 * idx)                                  # stagger starts so the free API isn't hammered
    for attempt in range(3):
        seed = base_seed if attempt == 0 else random.randint(1, 10**6)
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
               f"?width={GEN_W}&height={GEN_H}&nologo=true&seed={seed}")
        try:
            r = requests.get(url, headers=UA, timeout=45)
            if r.status_code == 200 and len(r.content) > 1000:
                img = Image.open(BytesIO(r.content))
                img.load()
                fit_and_save(img, path)
                return path
            log.warning("Scene %d: HTTP %s", idx, r.status_code)
            if r.status_code == 429:
                time.sleep(5)
        except Exception as e:  # noqa: BLE001
            log.warning("Scene %d attempt %d failed: %s", idx, attempt + 1, str(e)[:150])
        time.sleep(2 * (attempt + 1))
    log.warning("Scene %d: using gradient fallback", idx)
    return make_gradient(idx, path)


def safe_get_image(idx, prompt):
    try:
        return get_image(idx, prompt)
    except Exception as e:  # noqa: BLE001
        log.warning("Scene %d crashed (%s) - gradient fallback", idx, e)
        return make_gradient(idx, f"scene_{idx}.jpg")


def get_all_images(prompts):
    with ThreadPoolExecutor(max_workers=IMG_WORKERS) as ex:
        futures = [ex.submit(safe_get_image, i, p) for i, p in enumerate(prompts)]
        return [f.result() for f in futures]


# ---- stage 4: video ---------------------------------------------------------
def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return shutil.which("ffmpeg")


def audio_duration(path):
    exe = ffmpeg_exe()
    if exe:
        try:
            p = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True,
                               text=True, errors="replace", timeout=30)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
            if m:
                return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except Exception:  # noqa: BLE001
            pass
    try:
        from moviepy import AudioFileClip
    except ImportError:
        from moviepy.editor import AudioFileClip
    clip = AudioFileClip(path)
    try:
        return clip.duration
    finally:
        clip.close()


def render_ffmpeg(images, audio_path, out, total):
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg not found")
    n = len(images)
    per = total / n
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error"]
    for p in images:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{per:.3f}", "-i", p]
    cmd += ["-i", audio_path]
    graph = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0,format=yuv420p[v]"
    cmd += ["-filter_complex", graph, "-map", "[v]", "-map", f"{n}:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg exit {p.returncode}: {p.stderr[-300:]}")


def render_moviepy(images, audio_path, out, total):
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips   # v2
    except ImportError:
        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips  # v1
    per = total / len(images)
    audio, clips, video = AudioFileClip(audio_path), [], None
    try:
        for p in images:
            c = ImageClip(p)
            clips.append(c.with_duration(per) if hasattr(c, "with_duration") else c.set_duration(per))
        last = None
        for method in ("chain", "compose"):                 # chain is much faster; compose is the safe backup
            try:
                video = concatenate_videoclips(clips, method=method)
                video = video.with_audio(audio) if hasattr(video, "with_audio") else video.set_audio(audio)
                video.write_videofile(out, fps=FPS, codec="libx264", audio_codec="aac", preset="ultrafast",
                                      threads=os.cpu_count() or 2, ffmpeg_para
