import os, json, asyncio, requests, urllib.parse
from datetime import datetime
from google import genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# 1. Pick Niche Automatically Based on Time of Day
NICHES = [
    "Dark Psychology & Stoic Success Laws",
    "AI & Tech Money/Productivity Hacks",
    "Mind-Blowing Trivia & Riddles",
    "Bizarre Historical & Mystery Facts"
]
slot_index = datetime.utcnow().hour % 4
current_niche = NICHES[slot_index]

# 2. Generate Script & Image Prompts via Free Gemini API
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
prompt = f"""
You are the viral creator for 'Razzverse'. Write a 40-second YouTube Short / IG Reel in the niche: {current_niche}.
Return ONLY valid JSON in this exact format:
{{
  "title": "Viral Title under 60 chars #shorts",
  "caption": "Engaging caption for Instagram & YouTube with 5 viral hashtags #razzverse",
  "voiceover": "Full spoken script, punchy, no stage directions, around 95 words.",
  "image_prompts": [
    "Vertical 9:16 cinematic dark aesthetic illustration of...",
    "Vertical 9:16 ultra detailed scene of...",
    "Vertical 9:16 dramatic visual of...",
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

# 3. Generate Free Neural Voiceover (Edge-TTS)
async def make_Audio():
    communicate = edge_tts.Communicate(data["voiceover"], "en-US-ChristopherNeural", rate="+8%")
    await communicate.save("voice.mp3")

asyncio.run(make_Audio())
audio = AudioFileClip("voice.mp3")
scene_duration = audio.duration / len(data["image_prompts"])

# 4. Generate 4 Free AI Images (Pollinations API - No Key Required)
clips = []
for i, img_prompt in enumerate(data["image_prompts"]):
    encoded = urllib.parse.quote(img_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={i+100}"
    img_data = requests.get(url).content
    img_path = f"scene_{i}.jpg"
    with open(img_path, "wb") as f:
        f.write(img_data)
    clip = ImageClip(img_path).set_duration(scene_duration)
    clips.append(clip)

# 5. Render Final 9:16 MP4 Video
final_video = concatenate_videoclips(clips, method="compose").set_audio(audio)
final_video.write_videofile("razzverse_short.mp4", fps=24, codec="libx264", audio_codec="aac")

# 6. Save Metadata for Auto-Upload
with open("metadata.json", "w") as f:
    json.dump({"title": data["title"], "caption": data["caption"], "niche": current_niche}, f)

print("SUCCESS: Razzverse video rendered:", data["title"])
