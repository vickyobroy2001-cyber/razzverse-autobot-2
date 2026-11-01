#!/usr/bin/env python3
"""
Razzverse Shorts generator - hardened version.

pip install google-genai edge-tts moviepy requests pillow gTTS

Design rule: every stage has retries + a fallback, so the pipeline keeps going.
Only a total failure (no audio at all / video can't render) exits non-zero.
"""
import os
import re
import sys
import json
import time
import random
import asyncio
import logging
import traceback
import urllib.parse
from io import BytesIO
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

# ---- moviepy v2 / v1 compatibility -----------------------------------------
try:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips  # v2.x
except ImportError:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips  # v1.x


def _set_duration(clip, d):
    return clip.with_duration(d) if hasattr(clip, "with_duration") else clip.set_duration(d)


def _set_audio(clip, a):
    return clip.with_audio(a) if hasattr(clip, "with_audio") else clip.set_audio(a)


# ---- config -----------------------------------------------------------------
W, H = 1080, 1920
VOICE = os.environ.get("TTS_VOICE", "hi-IN-SwaraNeural")
OUT_VIDEO = "razzverse_short.mp4"
OUT_AUDIO = "voice.mp3"
OUT_META = "metadata.json"
UA = {"User-Agent": "Mozilla/5.0"}
PREFERRED_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
SKIP_MODEL_WORDS = ("image", "tts", "live", "embedding", "veo", "imagen", "aqa",
                    "robotics", "computer", "audio", "gemma", "learnlm")

NICHES = [
    "Psychology & Mind Tricks (इंसानी दिमाग और व्यवहार के रहस्य)",
    "AI & Tech Money/Productivity Hacks (AI और टेक्नोलॉजी से पैसे और समय बचाने के हैक्स)",
    "Science Trivia & Mystery (विज्ञान के ऐसे रहस्य जो दिमाग हिला दें)",
    "Bizarre Historical & Mystery Facts (इतिहास के सबसे अजीब और रहस्यमयी सच)",
]

# Used only if Gemini is completely unavailable, so the channel still posts.
FALLBACKS = [
    {
        "title": "Eye Contact Trick Jo Sabko Impress Kare #shorts #razzverse",
        "caption": "Ye psychology trick try karke bataiye! #razzverse #hindishorts #psychology #mindtricks #shorts",
        "theme": "two people talking, intense eye contact, psychology concept",
        "voiceover": "क्या आपको पता है? जब आप किसी की आँखों में देखकर बात करते हो, तो सामने वाला आप पर ज़्यादा भरोसा करता है! साइकोलॉजी कहती है कि तीन सेकंड का आई कॉन्टैक्ट आपको कॉन्फिडेंट दिखाता है। अगली बार किसी से बात करो तो ये ट्रिक ज़रूर आज़माना। और हाँ, ऐसे ही मज़ेदार फैक्ट्स के लिए रज़्ज़वर्स को फॉलो करना मत भूलना!",
    },
    {
        "title": "AI Se Roz 1 Ghanta Bachao #shorts #razzverse",
        "caption": "AI se time bachao! #razzverse #hindishorts #ai #productivity #shorts",
        "theme": "futuristic AI assistant helping a person work, glowing interface",
        "voiceover": "क्या आप जानते हो कि AI से आप रोज़ का एक घंटा बचा सकते हो? बस अपने बोरिंग काम, जैसे ईमेल लिखना या नोट्स बनाना, AI को दे दो। सिर्फ़ एक अच्छा सा प्रॉम्प्ट लिखो और काम मिनटों में खत्म! इसे आज ही ट्राई करो और टाइम बचाओ। ऐसे और हैक्स के लिए रज़्ज़वर्स को फॉलो करो!",
    },
    {
        "title": "Shahad Kabhi Kharab Kyun Nahi Hota? #shorts #razzverse",
        "caption": "Science ka kamaal! #razzverse #hindishorts #science #facts #shorts",
        "theme": "golden honey dripping, ancient Egyptian tomb, macro photography",
        "voiceover": "क्या आप जानते हो कि शहद कभी खराब नहीं होता? वैज्ञानिकों को मिस्र के मकबरों में हज़ारों साल पुराना शहद मिला, जो आज भी खाने लायक था! इसकी वजह है शहद में बहुत कम पानी और नेचुरल एंटीबैक्टीरियल गुण। है ना कमाल की साइंस? और भी ऐसे रहस्यों के लिए रज़्ज़वर्स को फॉलो करो!",
    },
    {
        "title": "Cleopatra Ka Hairaan Kar Dene Wala Sach #shorts #razzverse",
        "caption": "History ka ajeeb sach! #razzverse #hindishorts #history #mystery #shorts",
        "theme": "ancient Egypt pyramids at sunset, Cleopatra era, epic cinematic",
        "voiceover": "क्या आप जानते हो कि क्लियोपेट्रा पिरामिड बनने के वक़्त से ज़्यादा, चांद पर इंसान के उतरने के वक़्त के करीब थीं? सुनकर दिमाग घूम गया ना? इतिहास इतना लंबा है कि हमें समय का अंदाज़ा ही नहीं होता। ऐसे और अजीब सच जानने के लिए रज़्ज़वर्स को फॉलो करो!",
    },
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("razzverse")


# ---- helpers ----------------------------------------------------------------
def retry(fn, tries=3, delay=3, what="task"):
    last = None
    for i in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning("%s failed (%d/%d): %s", what, i, tries, e)
            if i < tries:
                time.sleep(delay * i)
    raise last


def themed_prompts(theme):
    angles = ["wide establishing shot", "close-up detail", "dramatic low angle",
              "moody atmospheric lighting", "glowing abstract concept art"]
    return [f"Vertical 9:16 cinematic 8k, {theme}, {a}, volumetric light, ultra detailed, no text"
            for a in angles]


def clean_voice(text):
    text = re.sub(r"#\w+", "", text)                      # hashtags
    text = re.sub(r"[*_`~<>\[\]{}|]", "", text)           # markdown junk
    text = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27BF]", "", text)  # emojis
    return re.sub(r"\s+", " ", text).strip()


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
    """Validate/repair the script dict. Returns None if unusable."""
    if not isinstance(d, dict):
        return None
    voice = clean_voice(str(d.get("voiceover", "")))
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
    prompts = prompts[:6]

    return {"title": title, "caption": caption, "voiceover": voice, "image_prompts": prompts}


def fallback_script(idx):
    fb = dict(FALLBACKS[idx])
    fb["image_prompts"] = themed_prompts(fb["theme"])
    return normalize(fb, idx)


# ---- stage 1: script (Gemini) -----------------------------------------------
def build_prompt(niche):
    return f"""You are the viral creator for 'Razzverse'. Write a 40-second YouTube Short / IG Reel in the niche: {niche}.
The speaker is a young, energetic, expressive Indian girl (like Alia Bhatt's bubbly, smart, conversational style).
Write the 'voiceover' in natural, spoken Hindi (Devanagari script) mixed with common English words (written in Devanagari, e.g., साइकोलॉजी, ट्रिक, AI, रिसर्च) so the Hindi TTS pronounces it natively.
No emojis, hashtags, asterisks or stage directions inside the voiceover.
Return ONLY valid JSON in this exact format:
{{"title": "Viral Hinglish/English Title under 60 chars #shorts #razzverse", "caption": "Engaging Hindi/Hinglish caption with 5 hashtags #razzverse #hindishorts", "voiceover": "Full spoken Hindi script in Devanagari, around 90 words.", "image_prompts": ["Detailed vertical 9:16 cinematic 8k prompt 1", "prompt 2", "prompt 3", "prompt 4", "prompt 5"]}}"""


def get_client():
    raw = os.environ.get("GEMINI_API_KEY", "")
    m = re.search(r"AIza[0-9A-Za-z\-_]{35}", raw)
    key = m.group(0) if m else raw.strip()
    if not key:
        log.warning("GEMINI_API_KEY is empty - will use fallback script")
        return None
    try:
        from google import genai
        return genai.Client(api_key=key)
    except Exception as e:  # noqa: BLE001
        log.warning("Gemini client unavailable: %s", e)
        return None


def candidate_models(client):
    models = []
    if os.environ.get("GEMINI_MODEL"):
        models.append(os.environ["GEMINI_MODEL"].strip())
    models += [m for m in PREFERRED_MODELS if m not in models]
    found = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if ("gemini" in name and name not in models and name not in found
                    and not any(w in name for w in SKIP_MODEL_WORDS)
                    and (not actions or "generateContent" in actions)):
                found.append(name)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not list models: %s", e)
    found.sort(reverse=True)                       # newer versions first
    found.sort(key=lambda n: "flash" not in n)     # flash models first
    return (models + found)[:8]


def get_script(client, idx):
    if client is None:
        return None
    prompt = build_prompt(NICHES[idx])
    for model in candidate_models(client):
        for attempt in range(1, 3):
            try:
                log.info("Trying %s (attempt %d)...", model, attempt)
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 1.0},
                )
                data = normalize(extract_json(res.text), idx)
                if data:
                    return data
                log.warning("%s returned unusable JSON", model)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                log.warning("Skip %s: %s", model, msg[:200])
                if any(x in msg for x in ("API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED")):
                    return None                    # bad key: no point trying more models
                if "404" in msg or "NOT_FOUND" in msg:
                    break                          # model retired: next model
                time.sleep(4 * attempt)            # 429 / 503: back off
    return None


# ---- stage 2: voice ---------------------------------------------------------
async def _edge_save(text, out, **prosody):
    import edge_tts
    await edge_tts.Communicate(text=text, voice=VOICE, **prosody).save(out)


def _audio_ok(path):
    return os.path.exists(path) and os.path.getsize(path) > 1000


def make_voice(text, out=OUT_AUDIO):
    for prosody in ({"rate": "+12%", "pitch": "+4Hz"}, {"rate": "+12%"}, {}):
        def attempt(p=prosody):
            if os.path.exists(out):
                os.remove(out)
            with ThreadPoolExecutor(1) as ex:      # safe even if a loop is already running
                ex.submit(asyncio.run, _edge_save(text, out, **p)).result()
            if not _audio_ok(out):
                raise RuntimeError("edge-tts produced empty audio")
        try:
            retry(attempt, tries=2, delay=3, what=f"edge-tts {prosody}")
            return out
        except Exception:  # noqa: BLE001
            continue

    log.warning("edge-tts failed - trying gTTS fallback")
    try:
        from gtts import gTTS
        retry(lambda: gTTS(text=text, lang="hi").save(out), tries=3, delay=3, what="gTTS")
        if _audio_ok(out):
            return out
    except Exception as e:  # noqa: BLE001
        log.error("gTTS fallback failed: %s", e)
    raise RuntimeError("No audio could be generated")


# ---- stage 3: images --------------------------------------------------------
def fit_and_save(img, path):
    """Cover-crop any image to exactly 1080x1920."""
    img = img.convert("RGB")
    scale = max(W / img.width, H / img.height)
    nw, nh = int(img.width * scale) + 1, int(img.height * scale) + 1
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    img.crop((left, top, left + W, top + H)).save(path, "JPEG", quality=92)


def make_gradient(idx, path):
    top = [(32, 20, 70), (70, 20, 60), (15, 50, 80), (60, 40, 20), (20, 60, 50)][idx % 5]
    bot = (8, 8, 20)
    col = Image.new("RGB", (1, H))
    col.putdata([tuple(int(top[c] + (bot[c] - top[c]) * y / H) for c in range(3)) for y in range(H)])
    col.resize((W, H)).save(path, "JPEG", quality=90)
    return path


def get_image(idx, prompt):
    path = f"scene_{idx}.jpg"
    for attempt in range(3):
        seed = idx + 100 if attempt == 0 else random.randint(1, 10**6)
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
               f"?width={W}&height={H}&nologo=true&seed={seed}")
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200 and len(r.content) > 1000:
                img = Image.open(BytesIO(r.content))
                img.load()
                fit_and_save(img, path)
                return path
            log.warning("Scene %d: HTTP %s", idx, r.status_code)
        except Exception as e:  # noqa: BLE001
            log.warning("Scene %d attempt %d failed: %s", idx, attempt + 1, e)
        time.sleep(3 * (attempt + 1))
    log.warning("Scene %d: using gradient fallback", idx)
    return make_gradient(idx, path)


# ---- stage 4: video ---------------------------------------------------------
def build_video(image_paths, audio_path, out=OUT_VIDEO):
    audio = AudioFileClip(audio_path)
    per = (audio.duration + 0.4) / len(image_paths)
    clips = [_set_duration(ImageClip(p), per) for p in image_paths]
    video = _set_audio(concatenate_videoclips(clips, method="compose"), audio)
    try:
        def render():
            video.write_videofile(out, fps=24, codec="libx264", audio_codec="aac",
                                  threads=2, ffmpeg_params=["-pix_fmt", "yuv420p"], logger=None)
        retry(render, tries=2, delay=3, what="render")
    finally:
        for c in clips + [video, audio]:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
    if not os.path.exists(out) or os.path.getsize(out) < 10_000:
        raise RuntimeError("Rendered video is missing or too small")


# ---- stage 5: publish -------------------------------------------------------
def upload_video(path):
    def post(url, extra):
        with open(path, "rb") as f:
            r = requests.post(url, data=extra, files={"fileToUpload": f}, headers=UA, timeout=180)
        link = r.text.strip()
        if r.status_code != 200 or not link.startswith("http"):
            raise RuntimeError(f"{r.status_code} {link[:120]}")
        return link

    hosts = [
        ("catbox", lambda: post("https://catbox.moe/user/api.php", {"reqtype": "fileupload"})),
        ("litterbox", lambda: post("https://litterbox.catbox.moe/resources/internals/api.php",
                                   {"reqtype": "fileupload", "time": "72h"})),
    ]
    for name, fn in hosts:
        try:
            return retry(fn, tries=3, delay=5, what=f"upload to {name}")
        except Exception as e:  # noqa: BLE001
            log.warning("%s upload gave up: %s", name, e)
    return ""


def notify_webhook(wh, data, video_url, path):
    payload = {"title": data["title"], "caption": data["caption"], "video_url": video_url}

    def with_file():
        with open(path, "rb") as f:
            r = requests.post(wh, data=payload, files={"file": (os.path.basename(path), f, "video/mp4")}, timeout=180)
        r.raise_for_status()

    def without_file():
        requests.post(wh, data=payload, timeout=60).raise_for_status()

    try:
        retry(with_file, tries=2, delay=5, what="webhook (with file)")
        return True
    except Exception:  # noqa: BLE001
        log.warning("Webhook with file failed - retrying with link only")
    try:
        retry(without_file, tries=3, delay=5, what="webhook (link only)")
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Webhook failed: %s", e)
        return False


# ---- main -------------------------------------------------------------------
def main():
    idx = datetime.now(timezone.utc).hour % 4
    log.info("Niche: %s", NICHES[idx])

    data = get_script(get_client(), idx)
    if not data:
        log.warning("Using built-in fallback script")
        data = fallback_script(idx)

    audio_path = make_voice(data["voiceover"])

    image_paths = []
    for i, p in enumerate(data["image_prompts"]):
        image_paths.append(get_image(i, p))
        time.sleep(1)  # be gentle with the free image API

    build_video(image_paths, audio_path)

    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("SUCCESS: Razzverse video rendered: %s", data["title"])

    wh = os.environ.get("MAKE_WEBHOOK_URL", "").strip()
    if not wh:
        return
    video_url = upload_video(OUT_VIDEO)
    if not video_url:
        log.warning("No public video URL - webhook will only get the attached file")
    if notify_webhook(wh, data, video_url, OUT_VIDEO):
        log.info("Webhook delivered")
    else:
        log.warning("Video is saved locally but the webhook was not delivered")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:  # noqa: BLE001
        log.error("FATAL:\n%s", traceback.format_exc())
        sys.exit(1)
