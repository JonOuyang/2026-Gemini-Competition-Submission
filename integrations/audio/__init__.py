"""
Audio Integration - Text-to-Speech and Speech-to-Text capabilities.

Provides:
- tts_speak: Text-to-speech via ElevenLabs API
- stop_speaking: Stop current audio playback
"""
from integrations.audio.tts import tts_speak, stop_speaking
