#!/usr/bin/env python3
"""
Razzverse MASTER - HD 3D Animated + MoneyPrinterTurbo + Brain Puzzle Edition
"""
import os, re, sys, math, json, time, wave, array, random, shutil, asyncio, logging, subprocess, urllib.parse
from io import BytesIO
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("razzverse-hd")

W, H, FPS = 1080, 1920, 24
DEFAULT_WEBHOOK = "https://hook.us2.make.com/dvt7x9d1fceu5vbr43snt0w8tyysw0dg"
OUT_VIDEO, OUT_AUDIO, OUT_BGM, OUT_META = "razzverse_short.mp4", "voice.mp3", "bgm.wav", "metadata.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

NICHES = [
    "Brain Puzzles, Detective Riddles & IQ Mind Training (दिमागी पहेलियाँ, जासूसी सवाल और IQ टेस्ट)",
    "Psychology & Dark Mind Tricks (दिमाग और मानव व्यवहार के गहरे रहस्य)",
    "Dark History & Untold Mysteries (इतिहास के रहस्यमयी और अनसुने पन्ने)",
    "Bizarre Science & Shocking Facts (दुनिया के अजीबोगरीब और चौंकाने वाले तथ्य)",
    "Success, Money & Power Laws (सफलता, पैसा और शक्ति के मनोवैज्ञानिक नियम)",
]

FALLBACK_PUZZLE = {
    "title": "Sirf 1% Genius Hi Ye Paheli Suljha Sakte Hain! 🧠 #shorts #razzverse",
    "caption": "Kya aapne sahi jawab pakda? Comment mein batao! 🧠🔥 #razzverse #paheli #riddles #iqtest #hindishorts #shorts",
    "voiceover": "सिर्फ एक प्रतिशत जीनियस ही इस जासूसी पहेली का सही जवाब दे सकते हैं! ध्यान से सुनो। एक अमीर आदमी अपने घर में मृत पाया गया। पुलिस ने तीन लोगों से पूछताछ की। रसोइए ने कहा वो नाश्ता बना रहा था। माली ने कहा वो पौधों को पानी दे रहा था। और नौकरानी ने कहा वो रविवार की सुबह डाक बॉक्स से चिट्ठियाँ ला रही थी। जासूस ने तुरंत नौकरानी को गिरफ्तार कर लिया! बताओ क्यों? सोचो... तीन, दो, एक! क्योंकि रविवार को डाक नहीं आती! क्या आपने सही पहचाना? कमेंट करो और रज़्ज़वर्स को फॉलो करो!",
    "search_terms": ["detective mystery", "thinking brain", "magnifying glass", "clock ticking", "genius mind", "crime scene"],
    "image_prompts": [
        "3D Unreal Engine 5 stylized animation vertical 9:16, mysterious detective standing in dark mansion, glowing clues, dramatic lighting, 8k HD",
        "3D Unreal Engine 5 stylized animation vertical 9:16, glowing human brain with golden puzzle pieces connecting, cinematic dark neon, 8k HD",
        "3D Unreal Engine 5 stylized animation vertical 9:16, three mysterious suspects in shadows under spotlight, suspense atmosphere, 8k HD",
        "3D Unreal Engine 5 stylized animation vertical 9:16, vintage red mailbox in rain with glowing question mark, dramatic angle, 8k HD",
        "3D Unreal Engine 5 stylized animation vertical 9:16, ticking golden pocket watch with glowing numbers 3 2 1, intense macro shot, 8k HD",
        "3D Unreal Engine 5 stylized animation vertical 9:16, detective pointing finger with shocked revelation lighting, cinematic 8k HD"
    ]
}

def build_prompt(idx):
    niche = NICHES[idx]
    is_puzzle = (idx == 0)
    style_rule = (
        "Write an interactive BRAIN PUZZLE / DETECTIVE RIDDLE / MIND TRAINING TEST. "
        "Start with a 3-second challenge hook ('सिर्फ 1% जीनियस ही...'). Present a short, clever mystery or brain puzzle with clues, "
        "include a suspense countdown ('सोचो... तीन, दो, एक!'), and reveal the smart answer at the end asking viewers to comment if they got it right."
        if is_puzzle else
        "Start with a 3-second shocking hook. Keep pacing fast, suspenseful, and end with a mind-blowing twist or question."
    )
    return f"""You are the viral creator for 'Razzverse'. Write a 45-second YouTube Short in the niche: {niche}.
{style_rule}
Write 'voiceover' in natural spoken Hindi (Devanagari script) mixed with common English words in Devanagari, around 100 words. No emojis or hashtags inside voiceover.
Provide 6 vivid 'image_prompts' in '3D Unreal Engine 5 stylized animation, vertical 9:16, dramatic glowing lighting, 8k HD, no text' style matching each part of the script, and 6 short English 'search_terms'.
Return ONLY valid JSON:
{{"title": "Catchy Hinglish Title #shorts #razzverse", "voiceover": "Spoken Hindi script...", "caption": "Engaging caption with 5 hashtags #razzverse #shorts", "search_terms": ["term1", "term2", "term3", "term4", "term5", "term6"], "image_prompts": ["3D animation prompt 1", "prompt 2", "prompt 3", "prompt 4", "prompt 5", "prompt 6"]}}"""

def get_script(idx):
    raw_key = os.environ.get("GEMINI_API_KEY", "")
    m = re.search(r"AIza[0-9A-Za-z\-_]{35}", raw_key)
    key = m.group(0) if m else raw_key.strip()
    if not key:
        return FALLBACK_PUZZLE
    prompt = build_prompt(idx)
    try:
        from google import genai
        client = genai.Client(api_key=key)
        for model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                log.info("Trying %s for niche [%d]...", model, idx)
                res = client.models.generate_content(model=model, contents=prompt, config={"response_mime_type": "application/json"})
                t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (res.text or "").strip(), flags=re.MULTILINE).strip()
                d = json.loads(t[t.find("{"):t.rfind("}")+1])
                voice = re.sub(r"[#*_`~<>\[\]{}|]", "", str(d.get("voiceover") or d.get("script") or "")).strip()
                if len(voice.split()) >= 18:
                    prompts = [str(p) for p in (d.get("image_prompts") or FALLBACK_PUZZLE["image_prompts"])][:6]
                    while len(prompts) < 6:
                        prompts.append(FALLBACK_PUZZLE["image_prompts"][len(prompts) % 6])
                    return {
                        "title": str(d.get("title") or FALLBACK_PUZZLE["title"])[:95],
                        "caption": str(d.get("caption") or FALLBACK_PUZZLE["caption"]),
                        "voiceover": voice,
                        "script": voice,
                        "image_prompts": prompts
                    }
            except Exception as e:
                log.warning("Skip %s: %s", model, str(e)[:120])
                time.sleep(2)
    except Exception as e:
        log.warning("Gemini error: %s", e)
    return FALLBACK_PUZZLE

async def _edge_tts_stream(text, voice, out_audio):
    import edge_tts
    comm = edge_tts.Communicate(text=text, voice=voice, rate="+8%")
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

def make_voice_and_subs(text, idx):
    voice = os.environ.get("TTS_VOICE") or ("hi-IN-MadhurNeural" if idx % 2 == 0 else "hi-IN-SwaraNeural")
    subs = []
    for _ in range(2):
        try:
            subs = asyncio.run(_edge_tts_stream(text, voice, OUT_AUDIO))
            if os.path.exists(OUT_AUDIO) and os.path.getsize(OUT_AUDIO) > 1000:
                break
        except Exception as e:
            log.warning("edge-tts retry: %s", e)
    if not (os.path.exists(OUT_AUDIO) and os.path.getsize(OUT_AUDIO) > 1000):
        from gtts import gTTS
        gTTS(text=text, lang="hi").save(OUT_AUDIO)

    phrases = []
    if subs:
        buf, c_start, c_end = [], 0.0, 0.0
        for s, e, w in subs:
            if not buf:
                c_start = s
            buf.append(w)
            c_end = max(e, s + 0.15)
            if len(buf) >= 4 or any(p in w for p in ("।", "?", "!", ",")):
                phrases.append((c_start, c_end, " ".join(buf)))
                buf = []
        if buf:
            phrases.append((c_start, c_end, " ".join(buf)))
    return OUT_AUDIO, phrases

def generate_suspense_bgm(duration_sec, out_wav=OUT_BGM):
    sr = 22050
    total_samples = int((duration_sec + 2.0) * sr)
    buf = array.array("h")
    for i in range(total_samples):
        t = i / sr
        # Deep cinematic sub-bass drone (55Hz + 110Hz) + subtle puzzle clock tick every 0.5s
        drone = 0.45 * math.sin(2 * math.pi * 55.0 * t) + 0.25 * math.sin(2 * math.pi * 110.0 * t)
        lfo = 0.6 + 0.4 * math.sin(2 * math.pi * 0.25 * t)
        phase = (t % 0.5)
        tick = math.exp(-phase * 45.0) * math.sin(2 * math.pi * 880.0 * t) * 0.35 if phase < 0.08 else 0.0
        val = int(max(-1.0, min(1.0, drone * lfo + tick)) * 14000)
        buf.append(val)
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(buf.tobytes())
    return out_wav

def get_hd_image(idx, prompt):
    path = f"scene_{idx}.jpg"
    time.sleep(0.35 * idx)
    styled = f"{prompt}, 3D stylized animation, Unreal Engine 5 render, vibrant glowing contrast, sharp focus, vertical 9:16, no text"
    for attempt in range(3):
        seed = int(time.time()) + idx * 17 + attempt * 101
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(styled)}?width={W}&height={H}&model=flux&nologo=true&seed={seed}"
        try:
            r = requests.get(url, headers=UA, timeout=45)
            if r.status_code == 200 and len(r.content) > 5000:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                resample = getattr(Image, "Resampling", Image).LANCZOS
                img = img.resize((W, H), resample)
                img = ImageEnhance.Contrast(img).enhance(1.12)
                img = ImageEnhance.Color(img).enhance(1.15)
                img.save(path, "JPEG", quality=95)
                return path
        except Exception as e:
            log.warning("Image %d retry %d: %s", idx, attempt + 1, str(e)[:100])
            time.sleep(2)
    img = Image.new("RGB", (W, H), (18, 12, 38))
    img.save(path, "JPEG", quality=92)
    return path

def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"

def get_audio_duration(exe, path):
    p = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
    return (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 40.0

def get_font():
    for c in ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(c):
            return ImageFont.truetype(c, 56)
    try:
        if not os.path.exists("NotoDevanagari.ttf"):
            r = requests.get("https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Bold.ttf", timeout=20)
            if r.status_code == 200:
                open("NotoDevanagari.ttf", "wb").write(r.content)
        return ImageFont.truetype("NotoDevanagari.ttf", 56)
    except Exception:
        return ImageFont.load_default()

def make_sub_banner(text, font, color_idx):
    banner_h = 300
    overlay = Image.new("RGBA", (W, banner_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    words = text.split()
    lines = [" ".join(words[:3]), " ".join(words[3:])] if len(words) > 3 else [text]
    lines = [l for l in lines if l.strip()]
    accent = (255, 230, 0, 255) if color_idx % 2 == 0 else (0, 240, 255, 255)

    # Measure box
    boxes = [draw.textbbox((0, 0), l, font=font) for l in lines]
    max_w = max((b[2] - b[0]) for b in boxes) if boxes else 400
    total_h = sum((b[3] - b[1]) for b in boxes) + 20 * len(lines)
    pad_x, pad_y = 42, 26
    bx1 = max(30, (W - max_w) // 2 - pad_x)
    bx2 = min(W - 30, (W + max_w) // 2 + pad_x)
    by1 = max(10, (banner_h - total_h) // 2 - pad_y)
    by2 = min(banner_h - 10, (banner_h + total_h) // 2 + pad_y)

    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=28, fill=(10, 10, 22, 210), outline=accent, width=4)
    curr_y = by1 + pad_y - 6
    for l, b in zip(lines, boxes):
        lw, lh = b[2] - b[0], b[3] - b[1]
        lx = (W - lw) // 2
        draw.text((lx, curr_y), l, font=font, fill=accent, stroke_width=4, stroke_fill=(0, 0, 0, 255))
        curr_y += lh + 22
    return overlay

def animate_crop(img, u, mode):
    # Smooth cosine easing for 3D camera motion (Zoom-In, Zoom-Out, Pan-LR, Pan-UD)
    e = 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, u)))
    if mode == 0:
        scale = 1.0 + 0.18 * e
        dx, dy = 0.5, 0.5
    elif mode == 1:
        scale = 1.18 - 0.18 * e
        dx, dy = 0.5, 0.5
    elif mode == 2:
        scale = 1.15
        dx, dy = e, 0.5
    else:
        scale = 1.15
        dx, dy = 0.5, 1.0 - e
    cw, ch = W / scale, H / scale
    x1 = (W - cw) * dx
    y1 = (H - ch) * dy
    resample = getattr(Image, "Resampling", Image).BILINEAR
    return img.resize((W, H), resample, box=(x1, y1, x1 + cw, y1 + ch))

def render_animated_video(image_paths, audio_path, phrases, script_text):
    exe = ffmpeg_exe()
    duration = max(6.0, get_audio_duration(exe, audio_path))
    bgm_path = generate_suspense_bgm(duration)
    font = get_font()

    if not phrases:
        words = script_text.split()
        chunks = [" ".join(words[i:i+4]) for i in range(0, len(words), 4)] or ["Razzverse"]
        cd = duration / len(chunks)
        phrases = [(i * cd, (i + 1) * cd, ch) for i, ch in enumerate(chunks)]

    # Pre-render subtitle banners once for speed
    sub_banners = [(s, e, make_sub_banner(txt, font, idx)) for idx, (s, e, txt) in enumerate(phrases)]
    imgs = [Image.open(p).convert("RGB").resize((W, H)) for p in image_paths]
    n_scenes = len(imgs)
    scene_dur = duration / n_scenes
    total_frames = int(duration * FPS)
    fade_sec = 0.35

    cmd = [
        exe, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-i", audio_path, "-i", bgm_path,
        "-filter_complex", "[1:a]volume=1.0[va];[2:a]volume=0.14[ba];[va][ba]amix=inputs=2:duration=first:dropout_transition=2[outa]",
        "-map", "0:v:0", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", OUT_VIDEO
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    for f_idx in range(total_frames):
        t = f_idx / FPS
        s_idx = min(n_scenes - 1, int(t / scene_dur))
        local_t = t - s_idx * scene_dur
        u = local_t / scene_dur
        frame = animate_crop(imgs[s_idx], u, s_idx % 4)

        # Smooth crossfade to next scene
        if s_idx < n_scenes - 1 and (scene_dur - local_t) < fade_sec:
            alpha = 1.0 - (scene_dur - local_t) / fade_sec
            next_frame = animate_crop(imgs[s_idx + 1], 0.0, (s_idx + 1) % 4)
            frame = Image.blend(frame, next_frame, max(0.0, min(1.0, alpha)))

        # Overlay MoneyPrinterTurbo pop-subtitle
        for s, e, banner in sub_banners:
            if s <= t <= e:
                frame.paste(banner, (0, H - 470), banner)
                break

        # Top viral retention progress bar
        draw = ImageDraw.Draw(frame)
        prog_w = int(W * (t / duration))
        draw.rectangle([0, 0, W, 12], fill=(30, 30, 45))
        draw.rectangle([0, 0, prog_w, 12], fill=(255, 215, 0))

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", errors="replace")
    proc.wait(timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg encode failed: {err[-300:]}")
    return OUT_VIDEO

def upload_and_notify(data):
    wh = os.environ.get("MAKE_WEBHOOK_URL", "").strip() or os.environ.get("MAKE_WEBHOOK_URL_3", "").strip() or DEFAULT_WEBHOOK
    pub_url = ""
    for host, extra in [("https://catbox.moe/user/api.php", {}), ("https://litterbox.catbox.moe/resources/internals/api.php", {"time": "72h"})]:
        try:
            with open(OUT_VIDEO, "rb") as f:
                r = requests.post(host, data={"reqtype": "fileupload", **extra}, files={"fileToUpload": f}, headers=UA, timeout=120)
            if r.status_code == 200 and r.text.strip().startswith("http"):
                pub_url = r.text.strip()
                log.info("Uploaded HD Video URL: %s", pub_url)
                break
        except Exception as e:
            log.warning("Upload host warning: %s", e)

    payload = {"title": data["title"], "caption": data["caption"], "script": data["voiceover"], "voiceover": data["voiceover"], "video_url": pub_url}
    open(OUT_META, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))

    try:
        with open(OUT_VIDEO, "rb") as f:
            r = requests.post(wh, data=payload, files={"file": (OUT_VIDEO, f, "video/mp4")}, timeout=120)
        log.info("Make.com Webhook (file) status: %s", r.status_code)
        if 200 <= r.status_code < 300:
            return
    except Exception as e:
        log.warning("Multipart webhook fallback: %s", e)
    r = requests.post(wh, json=payload, timeout=60)
    log.info("Make.com Webhook (JSON) status: %s", r.status_code)

def main():
    now = datetime.now(timezone.utc)
    # Cycles evenly across all 5 niches (including Brain Puzzles & Riddles)
    idx = (now.toordinal() * 4 + now.hour // 6) % len(NICHES)
    log.info("Selected Niche [%d]: %s", idx, NICHES[idx])
    data = get_script(idx)
    log.info("Script Ready: %s", data["title"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        vf = pool.submit(make_voice_and_subs, data["voiceover"], idx)
        imf = pool.submit(lambda: [get_hd_image(i, p) for i, p in enumerate(data["image_prompts"])])
        (audio_path, phrases), images = vf.result(), imf.result()

    render_animated_video(images, audio_path, phrases, data["voiceover"])
    upload_and_notify(data)
    log.info("SUCCESS: HD Animated Video rendered and delivered to Make.com!")

if __name__ == "__main__":
    main()
