import json
import subprocess
import sys
from pathlib import Path

# The clips file where all the clips are addressed
clips_json = Path("data/clips.json")

# The video file, it must match the video from which the full_transcript.json was extracted and from which clips.json was generated
input_video = Path("videos/video.mp4")

# The output for the clips
output_dir = Path("clips")
output_dir.mkdir(exist_ok=True)

####-----ENCODER------####
def get_video_encoder():
    """Check available encoders and select the best one."""

    # FFmpeg-এর encoder তালিকা সংগ্রহ করছি
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=True
    )

    # NVIDIA encoder পাওয়া গেলে GPU ব্যবহার করব
    if "h264_nvenc" in result.stdout:
        print("NVIDIA GPU encoder found! Using h264_nvenc.")
        return "h264_nvenc"

    # NVIDIA encoder না থাকলে CPU ব্যবহার করব
    print("NVIDIA GPU encoder not found. Using libx264.")
    return "libx264"

VIDEO_ENCODER = get_video_encoder()
# preset for the video
if VIDEO_ENCODER == "h264_nvenc":
    VIDEO_OPTIONS = ["-preset", "p4", "-cq", "23", "-b:v", "0"]
else:
    VIDEO_OPTIONS = ["-preset", "medium", "-crf", "23"]

####------------END----------####

def ids_are_continuous(segments):
    """Check if segment IDs form a perfect sequence with no gaps."""
    if not segments:
        print("Segments not found.")
        return False
    ids = [s["id"] for s in segments]
    return ids == list(range(ids[0], ids[-1] + 1))

def process_clip(clip, input_video, output_dir):
    clip_id = clip["id"]
    title = clip["recommended_title"]
    segments = clip["segments"]
    final_output = output_dir / f"clip_{clip_id}.mp4"

    print(f"\n--- Processing Clip {clip_id}: {title} ---")

    # Check if Segment IDs are perfectly sequential (no gaps in IDs)
    if ids_are_continuous(segments):
        # --- SINGLE CUT (IDs are continuous) ---
        start_time = segments[0]["start"]
        end_time = segments[-1]["end"]
        
        print(f"IDs continuous ({segments[0]['id']}–{segments[-1]['id']}). Single cut: {start_time}s → {end_time}s")
    
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(input_video),
            "-c:v", VIDEO_ENCODER,
            *VIDEO_OPTIONS,
            "-c:a", "aac",
            str(final_output)
        ]
        subprocess.run(cmd, check=True)
    else:
        # --- MULTI-CUT + CONCAT (IDs have gaps) ---
        ids = [s["id"] for s in segments]
        print(f"IDs have gaps {ids}. Cutting {len(segments)} parts and concatenating...")

        temp_files = []
        for idx, seg in enumerate(segments):
            temp_part = output_dir / f"temp_{clip_id}_{idx}.mp4"
            temp_files.append(temp_part)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(seg["start"]),
                "-to", str(seg["end"]),
                "-i", str(input_video),
                "-c:v", VIDEO_ENCODER,
                *VIDEO_OPTIONS,
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

#use this when importing
def create_clips(clip_ids=None):
    """Automatically makes all the clips that included in clips.json"""

    # Read clips from JSON
    with open(clips_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_clips = data["clips"]

    # If IDs provided, select only those clips
    if clip_ids is not None:
        all_clips = [
            clip for clip in all_clips
            if clip["id"] in clip_ids
        ]

    if not all_clips:
        print("No matching clips found.")
        return

    # Process selected clips
    for clip in all_clips:
        try:
            process_clip(clip, input_video, output_dir)
        except Exception as e:
            print(f"Error processing clip {clip['id']}: {e}")

if __name__ == "__main__":
    with open(clips_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_clips = data["clips"]

    # Parse command line arguments for specific clip IDs
    # Usage: python clip_maker.py [clip_id_1] [clip_id_2] ...
    target_ids = set()
    if len(sys.argv) > 1:
        try:
            target_ids = {int(arg) for arg in sys.argv[1:]}
        except ValueError:
            print("Error: Clip IDs must be integers.")
            sys.exit(1)

    # Filter clips if specific IDs provided
    clips_to_process = all_clips
    if target_ids:
        clips_to_process = [c for c in all_clips if c["id"] in target_ids]
        if not clips_to_process:
            print(f"No clips found with IDs: {target_ids}")
            sys.exit(1)
        print(f"Processing specific clips: {target_ids}")
    else:
        print("Processing all clips...")

    for clip in clips_to_process:
        try:
            process_clip(clip, input_video, output_dir)
        except subprocess.CalledProcessError as e:
            print(f"Error processing clip {clip['id']}: {e}")
        except Exception as e:
            print(f"Unexpected error processing clip {clip['id']}: {e}")

    print("\nDone! Clips saved in the clips/ directory.")
