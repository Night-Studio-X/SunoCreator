import json

with open("./data/full_transcript.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(len(data["segments"]))