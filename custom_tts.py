# custom_tts.py
import aiohttp
from pipecat.services.tts_service import TTSService
from pipecat.frames.frames import TTSStartedFrame, TTSAudioRawFrame, TTSStoppedFrame, ErrorFrame

class ResonovaTTSService(TTSService):
    def __init__(self, *, base_url, session, voice="fernanda-v1", sample_rate=24000, channels=1):
        super().__init__(sample_rate=sample_rate)
        self._base_url = base_url
        self._session = session
        self.voice = voice
        self.channels = channels

    async def run_tts(self, text: str):
        try:
            payload = {
                "model": "IndexTTS",
                "input": text,
                "voice": self.voice,
                "response_format": "wav",
                "sample_rate": self.sample_rate,
                "stream": True,
                "speed": 1.0,
                "gain": 0.0
            }
            headers = {
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json"
            }

            async with self._session.post(self._base_url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    yield ErrorFrame(f"TTS error: {await resp.text()}")
                    return
                yield TTSStartedFrame()
                
                first = True
                async for chunk in resp.content.iter_chunked(1024):
                    if first and chunk[:4] == b'RIFF':
                        chunk = chunk[44:]  # WAV header is 44 bytes
                        first = False
                    yield TTSAudioRawFrame(chunk, self.sample_rate, self.channels)
                yield TTSStoppedFrame()
                
        except Exception as e:
            yield ErrorFrame(str(e))

