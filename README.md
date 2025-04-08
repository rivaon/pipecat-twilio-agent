# Pipecat Twilio AI Agent

This project is a FastAPI-based chatbot that integrates with Twilio to handle WebSocket connections and provide real-time communication. The project includes endpoints for starting a call and handling WebSocket connections.
Customize the bot.py file to change the AI agent's behavior.
This is setup to save audio recordings to the server_0_recording.wav file.

## Installation

```console
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Install ngrok: Follow the instructions on the [ngrok website](https://ngrok.com/download) to download and install ngrok.

## Setup Environment

In this project's directory, run the following command to copy the `.env.example` file to `.env`:

```console
cp .env.example .env
```

Edit the `.env` file with your own values.

### OpenAI

Visit https://platform.openai.com to get your `OPENAI_API_KEY`.

### Deepgram

Visit https://deepgram.com to get your `DEEPGRAM_API_KEY`.

### ElevenLabs

Visit https://elevenlabs.io to get your `ELEVEN_API_KEY` and `ELEVEN_VOICE_ID`.

## Configure Twilio URLs

1. **Start ngrok**:
   In a new terminal, start ngrok to tunnel the local server:

   ```sh
   ngrok http 8765
   ```

2. **Update the Twilio Webhook**:

   - Go to your Twilio phone number's configuration page
   - Under "Voice Configuration", in the "A call comes in" section:
     - Select "Webhook" from the dropdown
     - Enter your ngrok URL (e.g., http://<ngrok_url>)
     - Ensure "HTTP POST" is selected
   - Click Save at the bottom of the page

3. **Configure streams.xml**:
   - Copy the template file to create your local version:
     ```sh
     cp templates/streams.xml.template templates/streams.xml
     ```
   - In `templates/streams.xml`, replace `<your server url>` with your ngrok URL (without `https://`)
   - The final URL should look like: `wss://abc123.ngrok.io/ws`

## Usage

**Run the FastAPI application**:

```sh
# Make sure you’re in the project directory and your virtual environment is activated
python server.py
```

The server will start on port 8765. Keep this running while you test with Twilio.

To start a call, simply make a call to your configured Twilio phone number. The webhook URL will direct the call to your FastAPI application, which will handle it accordingly.

## Testing

It is also possible to automatically test the server without making phone calls by using a software client.

First, update `templates/streams.xml` to point to your server's websocket endpoint. For example:

```
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="ws://localhost:8765/ws"></Stream>
  </Connect>
  <Pause length="40"/>
</Response>
```

Then, start the server with `-t` to indicate we are testing:

```sh
# Make sure you’re in the project directory and your virtual environment is activated
python server.py -t
```

Finally, just point the client to the server's URL:

```sh
python client.py -u http://localhost:8765 -c 2
```

where `-c` allows you to create multiple concurrent clients.

## Note

This follows the the [Pipecat Twilio Example](https://github.com/pipecat-ai/pipecat/blob/main/examples/twilio-chatbot/README.md) repository.