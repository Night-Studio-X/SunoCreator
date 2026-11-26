from pydantic_ai import Agent
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import json
from pathlib import Path
import time
from pydantic_ai.exceptions import ModelUnavailableError


load_dotenv()

instructions = """
You are an assistant that selects a compelling short-video transcript from a
long-form transcript supplied by the user.

Read the complete transcript and identify the most important, engaging material
that works as one coherent short video. Select original
transcript segments whose combined duration is as close to 60 seconds or below 120 seconds as possible.
Keep the selected segments in their original chronological order.

Return a structured response matching the requested schema. Each clip should
contain a concise hook, a recommended title, and the selected original transcript
segments with their IDs, start times, end times, and exact text.

Use only information and wording present in the supplied transcript. Do not invent
content, rewrite what the speaker said, or make up timestamps. Prefer complete
segments; if the transcript does not contain enough material for approximately
60 seconds, state that clearly instead of filling the gap with invented content.
"""

class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str


class ClipContent(BaseModel):
    id: int
    segments: list[TranscriptSegment]
    hook: str
    recommended_title: str


class ListContent(BaseModel):
    id: int
    clips: list[ClipContent] = Field(min_length=5)


agent = Agent(
    model="google:gemini-3.5-flash-lite",
    instructions=instructions,
    output_type=ListContent,
)


data_path = Path(__file__).resolve().parent / "data"
full_transcript_path = data_path / "full_transcript.json"
clips_path = data_path / "clips.json"

def generate_content_from_transcript():
    #loading the full_transcript jsonf file
    with full_transcript_path.open(encoding="utf-8",mode="r") as f:
        full_transcript = json.load(f) 

    video = full_transcript["video"]
    segments = full_transcript["segments"]

    prompt = {
        "video": video,
        "segments": [
            {
                "id": segment["id"],
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"]
            } for segment in segments
        ]
    }

    for attempt in range(3):
        try:
            response = agent.run_sync(json.dumps(prompt, ensure_ascii=False))
            clips_data = response.output
            clips_path.write_text(
                clips_data.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            return clips_data
        except ModelUnavailableError:
            if attempt == 2:
                raise
            wait_seconds = 2 ** (attempt + 1)
            print(f"Model unavailable; retrying in {wait_seconds}s...")
            time.sleep(wait_seconds)
            



if __name__ == "__main__":
    generate_content_from_transcript()
    print(f"Saved generated clips to {clips_path}")

