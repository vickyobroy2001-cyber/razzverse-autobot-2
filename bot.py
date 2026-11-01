import os, re, time, json, asyncio, requests, urllib.parse
from datetime import datetime
from google import genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, ColorClip

NICHES = [
"Dark Psychology & Mind Tricks (काली मनोविज्ञान और दिमाग के राज़)",
"AI & Tech Money/Productivity Hacks (AI और टेक्नोलॉजी से पैसे और समय बचाने के हैक्स)",
"Mind-Blowing Trivia & Riddles (दिमाग हिला देने वाले रोचक तथ्य और पहेलियां)",
"Bizarre Historical & Mystery Facts (इतिहास के सबसे अजीब और रहस्यमयी सच)"
]
current_niche = NICHES[datetime.utcnow().hour % 4]

raw_secret = os.environ.get("GEMINI_API_KEY", "")
match = re.search(r'(AIza[0-9A-Za-z\-_]+|AQ\.[0-9A-Za-z\-_]+)', raw_secret)
clean_key = match.group(1) if match else raw_secret.strip()
client = genai.Client(api_key=clean_key)

prompt = f"""You are the viral creator for 'Razzverse'. Write a 40-second YouTube Short / IG Reel in the niche: {current_niche}.
The speaker is a young, energetic, expressive Indian girl (like Alia Bhatt's bubbly, smart, conversational style).
Write the 'voiceover' in natural, spoken Hindi (Devanagari script) mixed with common English words (written in Devanagari, e.g., साइकोलॉजी, ट्रिक, माइंडसेट) so the Hindi TTS pronounces it naturally.
Return ONLY valid JSON in this exact format:
{{"title": "Viral Hinglish/Hindi Title under 60 chars #shorts #razzverse", "caption": "Engaging Hindi/Hinglish caption with 5 hashtags #razzverse #hindishorts", "voiceover": "Full spoken Hindi script in Devanagari, around 90 words.", "image_prompts": ["Vertical 9:16 dark aesthetic scene 1", "Vertical 9:16 dramatic scene 2", "Vertical 9:16 vibrant scene 3", "Vertical 9:16 mind-blowing scene 4"]}}"""

MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]

def get_script():
    try:
        for m in client.models.list():
            mn = m.name.replace("models/", "")
            if "gemini" in mn and mn not in MODELS and not any(x in mn for x in ["image", "tts", "live", "embedding", "veo"]): MODELS.append(mn)
    except Exception: pass
    for m_name in MODELS:
        for attempt in range(2):
            try:
                print(f"Trying {m_name}...")
                res = client.models.generate_content(model=m_name, contents=prompt, config={"response_mime_type": "application/json"})
                if res and res.text: return res.text
            except Exception as e:
                print(f"Skip {m_name}: {e}"); time.sleep(3)
    raise RuntimeError("All models busy")

raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", get_script().strip(), flags=re.MULTILINE).strip()
data = json.loads(raw_text)

asyncio.run(edge_tts.Communicate(text=data["voiceover"], voice="hi-IN-SwaraNeural", rate="+12%", pitch="+6Hz").save("voice.mp3"))
audio = AudioFileClip("voice.mp3")
dur = audio.duration / len(data["image_prompts"])

def get_clip(idx, p):
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p)}?width=1080&height=1920&nologo=true&seed={idx+200}"
    for _ in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=45)
            if r.status_code == 200 and len(r.content) > 1000:
                open(f"scene_{idx}.jpg", "wb").write(r.content)
                return ImageClip(f"scene_{idx}.jpg").set_duration(dur)
        except Exception: time.sleep(3)
    return ColorClip(size=(1080, 1920), color=(20, 20, 35), duration=dur)

clips = [get_clip(i, p) for i, p in enumerate(data["image_prompts"])]
concatenate_videoclips(clips, method="compose").set_audio(audio).write_videofile("razzverse_short.mp4", fps=24, codec="libx264", audio_codec="aac")
open("metadata.json", "w", encoding="utf-8").write(json.dumps({"title": data["title"], "caption": data["caption"], "niche": current_niche}, ensure_ascii=False))
print("SUCCESS: Razzverse Hindi video rendered:", data["title"])
wh = os.environ.get("MAKE_WEBHOOK_URL", "").strip()
wh = os.environ.get("MAKE_WEBHOOK_URL", "").strip()
pub_url = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files={"fileToUpload": open("razzverse_short.mp4", "rb")}).text.strip() if wh else ""
if wh: requests.post(wh, data={"title": data["title"], "caption": data["caption"], "video_url": pub_url}, files={"file": ("razzverse_short.mp4", open("razzverse_short.mp4", "rb"), "video/mp4")})
    
