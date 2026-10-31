import os, json, asyncio, requests, urllib.parse
from datetime import datetime
from google import genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# 1. Rotate Through Your 4 Razzverse Niches Daily
NICHES = [
    "Dark Psychology & Mind Tricks (काली मनोविज्ञान और दिमाग के राज़)",
    "AI & Tech Money/Productivity Hacks (AI और टेक्नोलॉजी से पैसे और समय बचाने के हैक्स)",
    "Mind-Blowing Trivia & Riddles (दिमाग हिला देने वाले रोचक तथ्य और पहेलियां)",
    "Bizarre Historical & Mystery Facts (इतिहास के सबसे अजीब और रहस्यमयी सच)"
]
slot_index = datetime.utcnow().hour % 4
current_niche = NICHES[slot_index]

# 2. Generate Conversational Hindi Script (Alia Bhatt / Modern Youth Vibe)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
prompt = f"""
You are the viral creator for 'Razzverse'. Write a 40-second YouTube Short / IG Reel in the niche: {current_niche}.
The speaker is a young, energetic, expressive Indian girl (like Alia Bhatt's bubbly, smart, conversational style).
Write the 'voiceover' in natural, spoken Hindi (Devanagari script) mixed with common English words (written in Devanagari, e.g., साइकोलॉजी, ट्रिक, माइंडसेट) so the Hindi TTS pronounces it naturally.
Return ONLY valid JSON in this exact format:
{{
  "title": "Viral Hinglish/Hindi Title under 60 chars #shorts #razzverse",
  "caption": "Engaging Hindi/Hinglish caption for Instagram & YouTube with 5 viral hashtags #razzverse #hindishorts #facts",
  "voiceover": "Full spoken Hindi script in Devanagari, punchy, expressive, no stage directions, around 95 words.",
  "image_prompts": [
    "Vertical 9:16 cinematic dark aesthetic illustration of...",
    "Vertical 9:16 ultra detailed dramatic scene of...",
    "Vertical 9:16 vibrant expressive visual of...",
    "Vertical 9:16 mind-blowing artwork of..."
  ]
}}
"""
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config={"response_mime_type": "application/json"}
)
data = json.loads(response.text)

# 3. Generate Youthful Hindi Female Voiceover (Tuned Pitch & Speed)
async def make_audio():
    # hi-IN-SwaraNeural tuned with +12% speed and +6Hz pitch for a young, lively female tone
    communicate = edge_tts.Communicate(
        text=data["voiceover"],
        voice="hi-IN-SwaraNeural",
        rate="+12%",
        pitch="+6Hz"
    )
    await communicate.save("voice.mp3")

asyncio.run(make_audio())
audio = AudioFileClip("voice.mp3")
scene_duration = audio.duration / len(data["image_prompts"])

# 4. Generate 4 Free Vertical AI Images (Pollinations API)
clips = []
for i, img_prompt in enumerate(data["image_prompts"]):
    encoded = urllib.parse.quote(img_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={i+200}"
    img_data = requests.get(url).content
    img_path = f"scene_{i}.jpg"
    with open(img_path, "wb") as f:
        f.write(img_data)
    clip = ImageClip(img_path).set_duration(scene_duration)
    clips.append(clip)

# 5. Render Final 9:16 MP4 Video
final_video = concatenate_videoclips(clips, method="compose").set_audio(audio)
final_video.write_videofile("razzverse_short.mp4", fps=24, codec="libx264", audio_codec="aac")

# 6. Auto-Send Video & Caption to Make.com (For YouTube & Instagram Auto-Upload)
webhook_url = os.environ.get("MAKE_WEBHOOK_URL")
if webhook_url:
    with open("razzverse_short.mp4", "rb") as video_file:
        requests.post(
            webhook_url,
            data={"title": data["title"], "caption": data["caption"], "niche": current_niche},
            files={"video": ("razzverse_short.mp4", video_file, "video/mp4")}
        )
    print("Uploaded to Make.com for YouTube & Instagram publishing!")

print("SUCCESS: Razzverse Hindi video rendered:", data["title"])
