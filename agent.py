from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import json
import os
from pathlib import Path
import time
from pydantic_ai.exceptions import ModelUnavailableError


load_dotenv()

instructions = """
You are an assistant that selects compelling short-video clips from a
long-form transcript supplied by the user.

Read the complete transcript and identify the most important, engaging material
that works as coherent short videos. For each clip, select original
transcript segments whose combined duration is as close to 60 seconds or below 120 seconds as possible.
Keep the selected segment IDs in their original chronological order without duplicates.

Return a structured response matching the requested schema. Each clip should
contain a concise hook, a recommended title, and ONLY the integer `segment_ids`
of the selected transcript segments. Do NOT echo back segment text, start times,
or end times.

Use only segment IDs present in the supplied transcript. Do not invent
segment IDs or content. Prefer complete segments.
"""


class ClipContent(BaseModel):
    id: int
    segment_ids: list[int] = Field(
        min_length=1,
        description="Ordered list of original transcript segment IDs included in this clip.",
    )
    hook: str
    recommended_title: str


class ListContent(BaseModel):
    id: int
    clips: list[ClipContent] = Field(min_length=5)


def _use_omnirouter() -> bool:
    return os.getenv("use-omnirouter", "").strip().lower() in {"true", "1", "yes"}


def _get_model():
    if _use_omnirouter():
        api_key = os.getenv("OMNIROUTE_API_KEY")
        base_url = os.getenv("OMNIROUTE_BASE_URL")
        if not api_key or not base_url:
            raise RuntimeError(
                "use-omnirouter is enabled, but OMNIROUTE_API_KEY or OMNIROUTE_BASE_URL is missing in .env."
            )
        model_name = os.getenv("OMNIROUTE_MODEL", "personal-combo-weak")
        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                base_url=base_url,
                api_key=api_key,
            ),
        )
    return "google:gemini-3.5-flash-lite"


agent = Agent(
    model=_get_model(),
    deps_type=set[int] | None,
    instructions=instructions,
    output_type=ListContent,
)


@agent.output_validator
def validate_segment_ids(ctx: RunContext[set[int] | None], output: ListContent) -> ListContent:
    valid_ids = ctx.deps
    for clip in output.clips:
        if len(set(clip.segment_ids)) != len(clip.segment_ids):
            raise ModelRetry(
                f"Clip {clip.id} contains duplicate segment IDs. Return unique segment IDs in chronological order."
            )
        if clip.segment_ids != sorted(clip.segment_ids):
            raise ModelRetry(
                f"Clip {clip.id} segment_ids are not in chronological order: {clip.segment_ids}."
            )
        if valid_ids is not None:
            invalid = [seg_id for seg_id in clip.segment_ids if seg_id not in valid_ids]
            if invalid:
                raise ModelRetry(
                    f"Clip {clip.id} references unknown segment IDs: {invalid}. "
                    "Only use segment IDs present in the supplied transcript."
                )
    return output


data_path = Path(__file__).resolve().parent / "data"
full_transcript_path = data_path / "full_transcript.json"
clips_path = data_path / "clips.json"


def generate_content_from_transcript():
    # loading the full_transcript json file
    with full_transcript_path.open(encoding="utf-8", mode="r") as f:
        full_transcript = json.load(f)

    video = full_transcript["video"]
    segments = full_transcript["segments"]
    valid_ids = {segment["id"] for segment in segments}

    prompt = {
        "video": video,
        "segments": [
            {
                "id": segment["id"],
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
            }
            for segment in segments
        ],
    }

    for attempt in range(3):
        try:
            response = agent.run_sync(
                json.dumps(prompt, ensure_ascii=False),
                deps=valid_ids,
            )
            clips_data = response.output
            clips_path.parent.mkdir(parents=True, exist_ok=True)
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

