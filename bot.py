import os, re, time, json, asyncio, requests, urllib.parse
from datetime import datetime
from google import genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, ColorClip

# 1. Rotate Through Your 4 Razzverse Niches Daily
NICHES = [
    "Dark Psychology & Mind Tricks (काली मनोविज्ञान और दिमाग के राज़)",
    "AI & Tech Money/Productivity Hacks (AI और टेक्नोलॉजी से पैसे और समय बचाने के हैक्स)",
    "Mind-Blowing Trivia & Riddles (दिमाग हिला देने वाले रोचक तथ्य और पहेलियां)",
    "Bizarre Historical & Mystery Facts (इतिहास के सबसे अजीब और रहस्यमयी सच)"
]
slot_index = datetime.utcnow().hour % 4
current_niche = NICHES[slot_index]

# 2. Clean API Key Automatically
raw_secret = os.environ.get("GEMINI_API_KEY", "")
match = re.search(r'(AIza[0-9A-Za-z\-_]+|AQ\.[0-9A-Za-z\-_]+)', raw_secret)
clean_key = match.group(1) if match else raw_secret.strip()
client = genai.Client(api_key=clean_key)

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

# 3. Massive Multi-Model Fallback List + Auto-Discovery
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro"
]

# Auto-discover any other available Gemini text models on your key
try:
    for m in client.models.list():
        
