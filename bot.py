#!/usr/bin/env python3
"""
Razzverse MASTER v2 - Real Moving Stock Video + Auto Thumbnail + Daily Kids Rhymes Edition
"""
import os, re, sys, math, json, time, wave, array, random, shutil, asyncio, logging, subprocess, urllib.parse
from io import BytesIO
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("razzverse-v2")

W, H, FPS = 1080, 1920, 24
DEFAULT_WEBHOOK = "https://hook.us2.make.com/dvt7x9d1fceu5vbr43snt0w8tyysw0dg"
OUT_VIDEO = "razzverse_short.mp4"
OUT_THUMB = "thumbnail.jpg"
OUT_AUDIO = "voice.mp3"
OUT_BGM = "bgm.wav"
OUT_META = "metadata.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Niche 0 & 1 = Daily Two Types of Nursery Rhymes | Niche 2-6 = Original Razzverse Niches
NICHES = [
    {
        "id": "rhyme_hindi",
        "name": "Hindi Kids Nursery Rhyme & Action Song (मज़ेदार हिंदी बालगीत)",
        "is_kids": True,
        "lang": "hi",
    },
    {
        "id": "rhyme_english",
        "name": "English Nursery Rhyme, Counting & Animal Learning Song",
        "is_kids": True,
        "lang": "en",
    },
    {
        "id": "brain_puzzle",
        "name": "Brain Puzzles, Detective Riddles & IQ Mind Training",
        "is_kids": False,
        "lang": "hi",
    },
    {
        "id": "psychology",
        "name": "Psychology & Dark Mind Tricks",
        "is_kids": False,
        "lang": "hi",
    },
    {
        "id": "dark_history",
        "name": "Dark History & Untold Mysteries",
        "is_kids": False,
        "lang": "hi",
    },
    {
        "id": "science_facts",
        "name": "Bizarre Science & Shocking Facts",
        "is_kids": False,
        "lang": "hi",
    },
    {
        "id": "success_laws",
        "name": "Success, Money & Power Laws",
        "is_kids": False,
        "lang": "hi",
    },
]

FALLBACK_SCRIPTS = {
    "rhyme_hindi": {
        "title": "Chuk Chuk Chali Railgaadi! 🚂 Fun Hindi Kids Rhyme #kids #rhymes #shorts",
        "thumb_text": "CHUK CHUK RAIL!",
        "caption": "Bacchon ke liye mazedaar naya Hindi Balgeet! 🚂✨ Like aur Subscribe karein! #hindirhymes #nurseryrhymes #kidssongs #balgeet #shorts",
        "voiceover": (
            "छुक छुक करती रेल चली, रंग बिरंगी खेल चली! "
            "आगे इंजन सीटी मारे, पीछे डिब्बे नाचें सारे! "
            "पप्पू बंदर बैठा आगे, हाथी राजा पीछे भागे! "
            "हरा सिग्नल जब है आता, इंजन झट से दौड़ लगाता! "
            "लाल बत्ती पर रुकती गाड़ी, हँसती खेलती दुनिया सारी! "
            "बोलो बच्चों छुक छुक छुक, चलो चलें हम घूमने सब!"
        ),
        "search_terms": [
            "colorful toy train kids",
            "happy children playing",
            "cute monkey animal",
            "baby elephant walking",
            "colorful balloons kids",
            "children laughing park",
        ],
    },
    "rhyme_english": {
        "title": "Jump & Count 1 to 5! 🐰 Fun Animal Nursery Rhyme #nurseryrhymes #kids #shorts",
        "thumb_text": "COUNT 1 TO 5!",
        "caption": "Sing, jump, and count from 1 to 5 with cute animals! 🐰🎵 #nurseryrhymes #kidssongs #learning #preschool #shorts",
        "voiceover": (
            "One little bunny hopping in the sun, clap your hands and let us have some fun! "
            "Two yellow ducklings swimming in the pond, quack quack quack all day long! "
            "Three happy puppies wagging every tail, running down the sunny garden trail! "
            "Four bright butterflies dancing in the sky, flapping pretty wings way up high! "
            "Five shining stars twinkling in the night, count with me, one two three four five!"
        ),
        "search_terms": [
            "cute bunny rabbit hopping",
            "yellow ducklings swimming",
            "happy puppies playing grass",
            "colorful butterfly flying",
            "twinkling night stars sky",
            "happy kids clapping hands",
        ],
    },
    "default": {
        "title": "Sirf 1% Genius Hi Ye Paheli Suljha Sakte Hain! 🧠 #shorts #razzverse",
        "thumb_text": "1% GENIUS TEST!",
        "caption": "Kya aapne sahi jawab pakda? Comment mein batao! 🧠🔥 #razzverse #paheli #riddles #iqtest #shorts",
        "voiceover": (
            "सिर्फ एक प्रतिशत जीनियस ही इस जासूसी पहेली का सही जवाब दे सकते हैं! ध्यान से सुनो। "
            "एक अमीर आदमी अपने घर में मृत पाया गया। पुलिस ने तीन लोगों से पूछताछ की। "
            "रसोइए ने कहा वो नाश्ता बना रहा था। माली ने कहा वो पौधों को पानी दे रहा था। "
            "और नौकरानी ने कहा वो रविवार की सुबह डाक बॉक्स से चिट्ठियाँ ला रही थी। "
            "जासूस ने तुरंत नौकरानी को गिरफ्तार कर लिया! बताओ क्यों? "
            "सोचो... तीन, दो, एक! क्योंकि रविवार को डाक नहीं आती! क्या आपने सही पहचाना? कमेंट करो!"
        ),
        "search_terms": [
            "detective mystery night",
            "glowing brain technology",
            "magnifying glass clues",
            "vintage mailbox rain",
            "clock ticking macro",
            "shocked person thinking",
        ],
    },
}


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def get_audio_duration(exe, path):
    p = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
    return (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 35.0


def build_prompt(niche):
    nid = niche["id"]
    if nid == "rhyme_hindi":
        topics = [
            "a playful wooden toy horse galloping through a village fair",
            "a colorful chuk-chuk toy train with funny animals",
            "dancing raindrops, paper boats, and happy peacocks",
            "a twinkling moon, stars, and a sleepy little kitten",
            "a cheerful little fish swimming in a sparkling river",
            "a friendly elephant and a naughty monkey eating mangoes",
        ]
        topic = random.choice(topics)
        return f"""Write a 100% ORIGINAL, super catchy 35-second Hindi Nursery Rhyme (Balgeet) for young kids about: {topic}.
Do NOT copy any existing movie song or copyrighted lyrics. Invent fresh, simple, bouncy rhyming lines in Devanagari Hindi (about 65-85 words) that kids love to repeat. No emojis inside voiceover.
Provide 6 joyful, concrete English 'search_terms' (2-3 words each) that will find bright real-life or animated stock videos on Pexels/Pixabay (e.g., "happy puppy playing", "colorful balloons", "cute horse running").
Provide 'thumb_text': 2 to 4 short punchy ALL-CAPS Hinglish words for the video thumbnail (e.g., "NANHA GHODA!").
Return ONLY valid JSON:
{{"title": "Catchy Hinglish Kids Rhyme Title #hindirhymes #shorts", "thumb_text": "SHORT HOOK!", "voiceover": "Original Hindi rhyme...", "caption": "Fun description with 5 kids hashtags", "search_terms": ["term1","term2","term3","term4","term5","term6"]}}"""

    if nid == "rhyme_english":
        topics = [
            "counting 1 to 5 with cute jumping animals",
            "learning rainbow colors with fruits and balloons",
            "happy animal sounds on a sunny farm",
            "wheels, boats, and airplanes zooming around",
            "brushing teeth and getting ready with a smile",
            "twinkling stars, sun, and fluffy clouds",
        ]
        topic = random.choice(topics)
        return f"""Write a 100% ORIGINAL, joyful 35-second English Nursery Rhyme & learning song for toddlers about: {topic}.
Use simple, bouncy rhyming couplets (about 65-85 words). No emojis inside voiceover.
Provide 6 vivid English 'search_terms' (2-3 words each) that match bright kids/animal/nature stock videos on Pexels/Pixabay.
Provide 'thumb_text': 2 to 4 short punchy ALL-CAPS English words for the thumbnail (e.g., "COUNT WITH ME!").
Return ONLY valid JSON:
{{"title": "Catchy English Kids Song Title #nurseryrhymes #shorts", "thumb_text": "SHORT HOOK!", "voiceover": "Original English rhyme...", "caption": "Fun description with 5 kids hashtags", "search_terms": ["term1","term2","term3","term4","term5","term6"]}}"""

    is_puzzle = (nid == "brain_puzzle")
    style = (
        "Write an interactive detective riddle / IQ test with a 3-second hook ('सिर्फ 1% जीनियस ही...'), clues, a 3-2-1 countdown, and a clever reveal."
        if is_puzzle else
        "Start with a 3-second shocking hook, fast pacing, and end with a mind-blowing twist."
    )
    return f"""You are a viral YouTube Shorts creator for 'Razzverse'. Niche: {niche['name']}.
{style}
Write 'voiceover' in natural spoken Hindi (Devanagari script, ~90 words, no emojis/hashtags inside voiceover).
Provide 6 cinematic English 'search_terms' (2-3 words each) that match stock video clips on Pexels/Pixabay.
Provide 'thumb_text': 2 to 4 short punchy ALL-CAPS Hinglish words for the thumbnail.
Return ONLY valid JSON:
{{"title": "Catchy Hinglish Title #shorts #razzverse", "thumb_text": "SHORT HOOK!", "voiceover": "Spoken Hindi script...", "caption": "Engaging caption with 5 hashtags", "search_terms": ["term1","term2","term3","term4","term5","term6"]}}"""


def get_script(niche):
    fallback = FALLBACK_SCRIPTS.get(niche["id"], FALLBACK_SCRIPTS["default"])
    raw_key = os.environ.get("GEMINI_API_KEY", "")
    m = re.search(r"AIza[0-9A-Za-z\-_]{35}", raw_key)
    key = m.group(0) if m else raw_key.strip()
    if not key:
        log.warning("GEMINI_API_KEY missing; using fallback script.")
        return fallback

    prompt = build_prompt(niche)
    try:
        from google import genai
        client = genai.Client(api_key=key)
        for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
            try:
                log.info("Generating script via %s for [%s]...", model, niche["id"])
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
                t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (res.text or "").strip(), flags=re.MULTILINE).strip()
                d = json.loads(t[t.find("{"):t.rfind("}") + 1])
                voice = re.sub(r"[#*_`~<>\[\]{}|]", "", str(d.get("voiceover") or "")).strip()
                terms = [str(x).strip() for x in (d.get("search_terms") or []) if str(x).strip()][:6]
                while len(terms) < 6:
                    terms.append(fallback["search_terms"][len(terms) % len(fallback["search_terms"])])
                if len(voice.split()) >= 18:
                    return {
                        "title": str(d.get("title") or fallback["title"])[:95],
                        "thumb_text": str(d.get("thumb_text") or fallback["thumb_text"])[:28].upper(),
                        "caption": str(d.get("caption") or fallback["caption"]),
                        "voiceover": voice,
                        "search_terms": terms,
                    }
            except Exception as e:
                log.warning("Model %s skipped: %s", model, str(e)[:120])
                time.sleep(2)
    except Exception as e:
        log.warning("Gemini error: %s", e)
    return fallback


async def _edge_tts_stream(text, voice, rate, pitch, out_audio):
    import edge_tts
    comm = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    subs = []
    with open(out_audio, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 10_000_000.0
                d = chunk["duration"] / 10_000_000.0
                subs.append((s, s + d, chunk["text"]))
    return subs


def make_voice_and_subs(text, niche):
    if niche["id"] == "rhyme_hindi":
        voice, rate, pitch = "hi-IN-SwaraNeural", "+4%", "+12Hz"
    elif niche["id"] == "rhyme_english":
        voice, rate, pitch = "en-US-AnaNeural", "+2%", "+8Hz"
    else:
        voice, rate, pitch = "hi-IN-MadhurNeural", "+8%", "+0Hz"

    subs = []
    for _ in range(2):
        try:
            subs = asyncio.run(_edge_tts_stream(text, voice, rate, pitch, OUT_AUDIO))
            if os.path.exists(OUT_AUDIO) and os.path.getsize(OUT_AUDIO) > 1000:
                break
        except Exception as e:
            log.warning("edge-tts retry: %s", e)

    if not (os.path.exists(OUT_AUDIO) and os.path.getsize(OUT_AUDIO) > 1000):
        from gtts import gTTS
        gTTS(text=text, lang=niche["lang"]).save(OUT_AUDIO)

    phrases = []
    if subs:
        buf, c_start, c_end = [], 0.0, 0.0
        for s, e, w in subs:
            if not buf:
                c_start = s
            buf.append(w)
            c_end = max(e, s + 0.18)
            if len(buf) >= 4 or any(p in w for p in ("।", "?", "!", ",", ".")):
                phrases.append((c_start, c_end, " ".join(buf)))
                buf = []
        if buf:
            phrases.append((c_start, c_end, " ".join(buf)))
    return OUT_AUDIO, phrases


def generate_bgm(duration_sec, is_kids, out_wav=OUT_BGM):
    sr = 22050
    total_samples = int((duration_sec + 2.0) * sr)
    buf = array.array("h")

    if is_kids:
        # Cheerful playful C-major xylophone/music-box melody for kids rhymes
        melody = [523.25, 659.25, 783.99, 659.25, 880.00, 783.99, 659.25, 587.33,
                  523.25, 587.33, 659.25, 783.99, 1046.50, 783.99, 659.25, 523.25]
        bass = [261.63, 261.63, 392.00, 392.00, 349.23, 349.23, 392.00, 261.63]
        beat_len = 0.32
        for i in range(total_samples):
            t = i / sr
            b_idx = int(t / beat_len)
            bt = t - b_idx * beat_len
            freq = melody[b_idx % len(melody)]
            bfreq = bass[(b_idx // 2) % len(bass)]
            env = math.exp(-bt * 8.5)
            tone = (0.55 * math.sin(2 * math.pi * freq * t) + 0.2 * math.sin(4 * math.pi * freq * t)) * env
            warm = 0.22 * math.sin(2 * math.pi * bfreq * t) * math.exp(-bt * 3.0)
            val = int(max(-1.0, min(1.0, tone + warm)) * 13000)
            buf.append(val)
    else:
        # Cinematic suspense drone + soft clock tick for puzzles & mysteries
        for i in range(total_samples):
            t = i / sr
            drone = 0.45 * math.sin(2 * math.pi * 55.0 * t) + 0.25 * math.sin(2 * math.pi * 110.0 * t)
            lfo = 0.6 + 0.4 * math.sin(2 * math.pi * 0.25 * t)
            phase = t % 0.5
            tick = math.exp(-phase * 45.0) * math.sin(2 * math.pi * 880.0 * t) * 0.35 if phase < 0.08 else 0.0
            val = int(max(-1.0, min(1.0, drone * lfo + tick)) * 14000)
            buf.append(val)

    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(buf.tobytes())
    return out_wav


def _fetch_pexels_video(query, used_ids):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return None
    headers = {"Authorization": key, **UA}
    for orient in ("portrait", ""):
        try:
            params = {"query": query, "per_page": 10}
            if orient:
                params["orientation"] = orient
            r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=20)
            if r.status_code != 200:
                continue
            for v in r.json().get("videos", []):
                vid = f"pexels_{v.get('id')}"
                if vid in used_ids:
                    continue
                files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("link")]
                if not files:
                    continue
                # Prefer 720p-1080p clips so download & render stay fast and crisp
                files.sort(key=lambda f: abs((f.get("height") or 720) - 1280))
                used_ids.add(vid)
                return files[0]["link"]
        except Exception as e:
            log.warning("Pexels search warning (%s): %s", query, str(e)[:100])
    return None


def _fetch_pixabay_video(query, used_ids):
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return None
    try:
        r = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": key, "q": query, "per_page": 10, "safesearch": "true"},
            headers=UA,
            timeout=20,
        )
        if r.status_code != 200:
            return None
        for hit in r.json().get("hits", []):
            vid = f"pixabay_{hit.get('id')}"
            if vid in used_ids:
                continue
            vids = hit.get("videos", {})
            link = (vids.get("medium") or vids.get("large") or vids.get("small") or {}).get("url")
            if link:
                used_ids.add(vid)
                return link
    except Exception as e:
        log.warning("Pixabay search warning (%s): %s", query, str(e)[:100])
    return None


def _make_animated_fallback_clip(exe, idx, query, dur, is_kids):
    """Fallback ONLY if both Pexels & Pixabay fail: fetches a colorful photo and turns it into a smooth moving zoom/pan clip."""
    img_path = f"fallback_{idx}.jpg"
    out_clip = f"norm_{idx}.mp4"
    style = "bright Pixar 3D cartoon kids illustration colorful sunny" if is_kids else "cinematic HD photography dramatic lighting"
    prompt = f"{query}, {style}, vertical 9:16, no text"
    saved = False
    for attempt in range(2):
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width={W}&height={H}&nologo=true&seed={int(time.time()) + idx * 31 + attempt}"
        try:
            r = requests.get(url, headers=UA, timeout=35)
            if r.status_code == 200 and len(r.content) > 6000:
                img = Image.open(BytesIO(r.content)).convert("RGB").resize((W, H))
                img.save(img_path, "JPEG", quality=92)
                saved = True
                break
        except Exception:
            time.sleep(1.5)

    if not saved:
        # Vibrant gradient fallback so we NEVER get a dark blank screen
        img = Image.new("RGB", (W, H), (255, 190, 40) if is_kids else (30, 45, 95))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            c = int(255 * y / H)
            color = (255, max(80, 220 - c // 2), min(255, 60 + c // 2)) if is_kids else (20 + c // 8, 35 + c // 6, 90 + c // 4)
            draw.line([(0, y), (W, y)], fill=color)
        img.save(img_path, "JPEG", quality=90)

    frames = max(24, int(dur * FPS))
    zp = f"scale=1280:2276,zoompan=z='min(zoom+0.0018,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},format=yuv420p"
    subprocess.run([exe, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", img_path, "-t", f"{dur:.2f}", "-vf", zp, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-an", out_clip], check=True)
    return out_clip


def fetch_moving_clips(exe, search_terms, total_dur, is_kids):
    n = len(search_terms)
    clip_dur = max(3.5, total_dur / n)
    used_ids = set()
    generic_fallbacks = (
        ["happy children playing", "cute puppy dog", "colorful balloons", "rainbow nature", "cute cat", "butterflies flowers"]
        if is_kids else
        ["abstract neon lights", "city night traffic", "galaxy stars space", "clock time", "ocean waves", "mystery forest"]
    )

    norm_clips = []
    for i, term in enumerate(search_terms):
        raw_path = f"raw_{i}.mp4"
        norm_path = f"norm_{i}.mp4"
        video_url = None

        for q in (term, generic_fallbacks[i % len(generic_fallbacks)]):
            video_url = _fetch_pexels_video(q, used_ids) or _fetch_pixabay_video(q, used_ids)
            if video_url:
   
