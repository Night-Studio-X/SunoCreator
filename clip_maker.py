import json
import subprocess
from pathlib import Path

# The clips file where all the clips are addressed
clips_json = Path("data/clips.json")

# The video file, it must match the video from which the full_transcript.json was extracted and from which clips.json was generated
input_video = Path("videos/video.mp4")

# The output for the clips
output_dir = Path("clips")
output_dir.mkdir(exist_ok=True)

with open(clips_json, "r", encoding="utf-8") as f:
    data = json.load(f)

# loops through all the clips
for clip in data["clips"]:
    clip_id = clip["id"]
    title = clip["recommended_title"]
    segments = clip["segments"]
    final_output = output_dir / f"clip_{clip_id}.mp4"

    print(f"\n--- Processing Clip {clip_id}: {title} ---")

    # Some clips have 1 continious span of segments like all the segments start and end are connected to each other
    # and some have haves between them

    # If the clip has only 1 continuous span(connected to each other)
    if len(segments) == 1 or all(segments[i]["end"] == segments[i+1]["start"] for i in range(len(segments)-1)):
        start = segments[0]["start"]
        end = segments[-1]["end"]
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-to", str(end),
            "-i", str(input_video),
            "-c:v", "libx264",
            "-c:a", "aac",
            str(final_output)
        ]
        subprocess.run(cmd, check=True)
    else:
        # If segments have gaps, cut each part then concatenate(not connected to each other)
        temp_files = []
        for idx, seg in enumerate(segments):
            temp_part = output_dir / f"temp_{clip_id}_{idx}.mp4"
            temp_files.append(temp_part)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(seg["start"]),
                "-to", str(seg["end"]),
                "-i", str(input_video),
                "-c:v", "libx264",
                "-c:a", "aac",
                str(temp_part)
            ]
            subprocess.run(cmd, check=True)

        # Write list of parts to concatenate
        concat_txt = output_dir / f"concat_{clip_id}.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for tf in temp_files:
                f.write(f"file '{tf.resolve().as_posix()}'\n")

        # Merge parts into final clip
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(final_output)
        ]
        subprocess.run(concat_cmd, check=True)

        # Clean up temporary parts
        concat_txt.unlink(missing_ok=True)
        for tf in temp_files:
            tf.unlink(missing_ok=True)

    print(f"Created: {final_output}")

print("\nDone! All clips are saved in the clips/ directory.")
