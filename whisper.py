from faster_whisper import WhisperModel
import json
from pathlib import Path

# try:
#     model = WhisperModel(
#         "base",
#         device="cuda",
#         compute_type="float16",
#     )
#     print("Model loaded in cuda")

# except Exception:
#     model = WhisperModel(
#         "base",
#         device="cpu",
#         compute_type="int8",
#     )
#     print("Model loaded in cpu")

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("getting segments")
segments, info = model.transcribe(
    "videos/video.mp4",
    word_timestamps=True,
    log_progress=True
)
print("done")

result = {
    "video": {
        "filename": "video.mp4",
        "duration": round(info.duration, 2),
        "language": info.language,
    },
    "segments": [],
}

for segment in segments:
    words = []

    if segment.words:
        for word in segment.words:
            words.append({
                "start": round(word.start, 2),
                "end": round(word.end, 2),
                "word": word.word.strip(),
            })

    result["segments"].append({
        "id": len(result["segments"]) + 1,
        "start": round(segment.start, 2),
        "end": round(segment.end, 2),
        "text": segment.text.strip(),
        "words": words,
    })

output_path = Path("data/full_transcript.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

with output_path.open("w", encoding="utf-8") as file:
    json.dump(result, file, ensure_ascii=False, indent=2)

print(f"Transcription completed: {output_path}")
print(f"Total segments: {len(result['segments'])}")