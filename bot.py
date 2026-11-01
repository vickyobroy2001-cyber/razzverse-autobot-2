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

