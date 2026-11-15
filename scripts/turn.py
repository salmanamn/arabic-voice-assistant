"""One turn of the assistant on the laptop: speech in -> text -> answer -> speech out.

uv run python scripts/turn.py "ما هي عاصمة مملكة البحرين؟"    the question is spoken by Piper first (no microphone yet)
uv run python scripts/turn.py --wav my-question.wav            a recording of your own voice

Writes out/turn-question.wav (text input only) and out/turn-reply.wav.
"""

import argparse
import sys
from pathlib import Path

import openai

from voice.llm import Assistant
from voice.settings import load
from voice.stt import SpeechToText
from voice.textnorm import arabic_ratio, clean_for_speech
from voice.tts import TextToSpeech

OUT = Path("out")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("question", nargs="?", help="question as text; Piper speaks it to make the input audio")
    source.add_argument("--wav", type=Path, help="question as an audio file")
    args = parser.parse_args()

    settings = load()
    tts = TextToSpeech.from_settings(settings)
    stt = SpeechToText.from_settings(settings)
    assistant = Assistant.from_settings(settings)
    OUT.mkdir(exist_ok=True)

    if args.wav:
        question_wav = args.wav
    else:
        question_wav = OUT / "turn-question.wav"
        question_wav.write_bytes(tts.synthesize(args.question).wav)

    heard = stt.transcribe(question_wav)
    print(
        f"heard   {heard.seconds:5.2f} s  ({heard.audio_seconds:.1f} s of audio, {settings.stt_model})  | {heard.text}"
    )
    if not heard.text:
        print("no speech recognised in the input; nothing sent to the model")
        return 1

    try:
        reply = assistant.reply(heard.text)
    except openai.APIConnectionError:
        print(f"FAIL no answer from {settings.openai_base_url}: is Ollama up? (docker compose up -d)")
        return 2
    except openai.NotFoundError as exc:
        print(f"FAIL {settings.chat_model} is not available at {settings.openai_base_url}: {exc.message}")
        return 2
    spoken_text = clean_for_speech(reply.text)
    print(
        f"answer  {reply.seconds:5.2f} s  ({reply.completion_tokens} tokens, {settings.chat_model}, "
        f"{arabic_ratio(spoken_text):.0%} Arabic letters)  | {spoken_text}"
    )
    if not spoken_text:
        print("the model returned no text")
        return 1

    speech = tts.synthesize(spoken_text)
    reply_wav = OUT / "turn-reply.wav"
    reply_wav.write_bytes(speech.wav)
    print(f"spoken  {speech.seconds:5.2f} s  ({speech.audio_seconds:.1f} s of audio)  | {reply_wav}")
    print(f"total   {heard.seconds + reply.seconds + speech.seconds:5.2f} s from end of question to reply audio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
