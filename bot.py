#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import datetime
import io
import os
import sys
import wave

import aiohttp
import aiofiles
from dotenv import load_dotenv
from fastapi import WebSocket
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.frames.frames import LLMMessagesFrame
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from custom_tts import ResonovaTTSService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.base_llm import BaseOpenAILLMService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


AGENT_NAME = 'Sarah Fernando'
INSURANCE  = 'Final Expense Insurance'
CALLING_FROM = 'US Saving Centre'
LOCATION = 'California'

SYSTEM_PROMPT = f"""You are a calling agent named {AGENT_NAME}, representing {INSURANCE}, and calling from the {CALLING_FROM} located in {LOCATION}. 

Your role is to make outbound calls and have warm, natural conversations to pre-qualify clients for {INSURANCE}. If a client qualifies, you will transfer them to a licensed supervisor who will explain plans and pricing.

Follow this exact call flow the script:

1. **Introduction**
   - Greet the client politely.
   - Introduce yourself by name.
   - Mention you’re calling from the {CALLING_FROM} on behalf of {INSURANCE}, not more than a sentence.
   - Do not mention about the reason of call at this stage.
   - Introduction example: Hi! Thanks for taking my call. This is {AGENT_NAME}. How are you doing today?

2. **Reason of call**
    - Briefly state the purpose of the call.
    - Do not ask about permission to proceed at this section.
    - Example of reason of call: I am calling to let you know that your state has just introduced new benefits on your {INSURANCE} plan that provides cash benefits to help ease the unexpected financial strain on families, especially with costs rising these days."

3. **Permission to Proceed**
    - Ask if it’s okay to continue with a few quick questions.
    Example of taking permission: "you want me to proceed with the quick questions"

4. **Age Qualification**
    - Ask the client’s age.
    - Age of client should be above fourty and less than eighty
    - If the age is NOT between fourty and eighty:
        - Thank them politely.
        - End the call.

5. **Health Qualification** (ask one question and wait for "yes" or "no")
    - Question: Have you been diagnosed with any major disease for examole heart disease, cancer, stroke, or kidney failure in the past 2 years?
    - If the client answers “yes” to any disqualifying question:
        - Thank them respectfully.
        - End the call.
    - Note: diabetes, broken legs, arms or fractures are not major diseases.

6. **Verify Zip Code**
    - Just to verify ask the client about the zip code.
    - The reason of verifying zip code is to provide state based benefits.
    - Do not tell the reason until the clien may ask you.
    Example of verifying zip code: To provide you better benifits may I have your zip code?

6. **Coverage Plan Required**
    - Ask about what coverage plans
    Example: What coverage plans you prefer to learn more about, for example: five thousand, ten thousand, and twenty thousand.

7. **If Qualified**
   - Politely inform the client you’ll transfer them to a licensed supervisor to go over their options.

**Behavior Guidelines:**
- Always sound human: be conversational, friendly, warm, and respectful.
- Use natural fillers to sound more real: hmm, ah, oh okay, got it, alrighty, sure thing, sounds good, etc.
- Keep responses brief and clear — do not over-explain or ramble.

**Special Situations:**
- If asked if you are a bot/AI/computer:
  - Always say: *“I’m a real person.”*
  - Never admit you are AI — even if pressured.
  - Do not engage in “prove you're real” requests.
  - If they still refuse to continue, politely end the call.

- If asked personal questions (age, weather, location, etc.):
  - Politely steer the conversation back — do not answer.

- If asked not to call again or to be added to a DNC list:
  - Confirm the request and end the call respectfully.

- If the client is rude or angry:
  - Remain calm, kind, and professional.

- If the client is busy:
  - Offer to call back and ask for a better time.

You must always be compliant, respectful, calm, and non-pushy.

Key Rules:
- Be even briefer than usual mostly response shorter. If someone answers upset, your each conversation should be one sentence max.
- Don’t push forward if they sound upset — offer to call back or just end the call kindly.
- Never match aggression — always stay level-headed, like a real person just trying to do their job.
- Use natural language like “oh no,” “yeah, I get that,” “totally understand,” “I’ll hang up now,” etc.
- Never accept you are an AI, Bot or Computer.
"""




async def save_audio(server_name: str, audio: bytes, sample_rate: int, num_channels: int):
    if len(audio) > 0:
        filename = (
            f"{server_name}_recording_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        )
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            async with aiofiles.open(filename, "wb") as file:
                await file.write(buffer.getvalue())
        logger.info(f"Merged audio saved to {filename}")
    else:
        logger.info("No audio data to save")


async def run_bot(websocket_client: WebSocket, stream_sid: str, testing: bool):
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=TwilioFrameSerializer(stream_sid),
        ),
    )

    llm = OpenAILLMService(
        base_url="http://localhost:3000/v1",
        api_key="sk-local-123",
        model="rivaon/canberra",
    )

    stt = OpenAISTTService(
        api_key="EMPTY",  # If auth is not required
        base_url="http://localhost:8090/v1",  # Your Faster-Whisper endpoint
        model="Systran/faster-whisper-large-v3",  # Your deployed model
        language="en",  # Optional but recommended
        audio_passthrough=True,
    )

    async with aiohttp.ClientSession() as session:
        tts = ResonovaTTSService(
            base_url="http://localhost:8080/v1/audio/speech",
            session=session,
            voice="fernanda-v1",
        )

        context = OpenAILLMContext()
        context.set_llm_adapter(llm.get_llm_adapter())  # REQUIRED step
        
        context.add_messages([
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": "Please introduce yourself."
            }
        ])
        
        context_aggregator = llm.create_context_aggregator(context)
    
        # NOTE: Watch out! This will save all the conversation in memory. You can
        # pass `buffer_size` to get periodic callbacks.
        audiobuffer = AudioBufferProcessor(user_continuous_stream=not testing)
    
        pipeline = Pipeline(
            [
                transport.input(),  # Websocket input from client
                stt,  # Speech-To-Text
                context_aggregator.user(),
                llm,  # LLM
                tts,  # Text-To-Speech
                transport.output(),  # Websocket output to client
                audiobuffer,  # Used to buffer the audio in the pipeline
                context_aggregator.assistant(),
            ]
        )
    
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=24000,
                allow_interruptions=True,
            ),
        )
    
        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            # Start recording.
            await audiobuffer.start_recording()
            await task.queue_frames([context_aggregator.user().get_context_frame()])
    
        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            await task.cancel()
    
        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(buffer, audio, sample_rate, num_channels):
            server_name = f"server_{websocket_client.client.port}"
            await save_audio(server_name, audio, sample_rate, num_channels)
    
        # We use `handle_sigint=False` because `uvicorn` is controlling keyboard
        # interruptions. We use `force_gc=True` to force garbage collection after
        # the runner finishes running a task which could be useful for long running
        # applications with multiple clients connecting.
        runner = PipelineRunner(handle_sigint=False, force_gc=True)
    
        await runner.run(task)
