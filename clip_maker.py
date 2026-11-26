import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import subprocess
import threading
from pathlib import Path

# The clips file where all the clips are addressed
clips_json = Path("data/clips.json")

# The full transcript file used to resolve segment IDs to timestamps
transcript_json = Path("data/full_transcript.json")

# The video file, it must match the video from which the full_transcript.json was extracted and from which clips.json was generated
input_video = Path("videos/video.mp4")

# The output for the clips
output_dir = Path("clips")
output_dir.mkdir(exist_ok=True)

_print_lock = threading.Lock()


def log(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


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

    # NVIDIA encoder পাওয়া গেলে GPU আসলেই কাজ করে কি না যাচাই করব
    if "h264_nvenc" in result.stdout:
        probe = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=black:s=64x64:d=0.1",
                "-frames:v", "1", "-c:v", "h264_nvenc",
                "-f", "null", "-",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            print("NVIDIA GPU encoder found! Using h264_nvenc.")
            return "h264_nvenc"

    # NVIDIA encoder না থাকলে CPU ব্যবহার করব
    print("NVIDIA GPU encoder not available. Using libx264.")
    return "libx264"


VIDEO_ENCODER = get_video_encoder()
# preset for the video and default parallel worker limit
if VIDEO_ENCODER == "h264_nvenc":
    VIDEO_OPTIONS = ["-preset", "p4", "-cq", "23", "-b:v", "0"]
    # Consumer NVIDIA GPUs cap concurrent NVENC sessions
    DEFAULT_MAX_WORKERS = 3
else:
    VIDEO_OPTIONS = ["-preset", "veryfast", "-crf", "23"]
    DEFAULT_MAX_WORKERS = 2

####------------END----------####


def load_segments_by_id(transcript_path: Path) -> dict[int, dict]:
    """Load full transcript segments indexed by segment ID."""
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = json.load(f)
    return {seg["id"]: seg for seg in transcript["segments"]}


def resolve_clip_segments(clip: dict, segments_by_id: dict[int, dict]) -> list[dict]:
    """Resolve a clip's segment_ids into full segment dicts containing start/end timestamps."""
    if "segment_ids" in clip:
        segment_ids = clip["segment_ids"]
        missing = [seg_id for seg_id in segment_ids if seg_id not in segments_by_id]
        if missing:
            raise ValueError(
                f"Clip {clip['id']} references unknown segment IDs not found in {transcript_json}: {missing}"
            )
        return [segments_by_id[seg_id] for seg_id in segment_ids]

    # Backwards compatibility if a legacy clips.json with 'segments' is supplied
    if "segments" in clip:
        raw_segments = clip["segments"]
        if raw_segments and isinstance(raw_segments[0], int):
            missing = [seg_id for seg_id in raw_segments if seg_id not in segments_by_id]
            if missing:
                raise ValueError(
                    f"Clip {clip['id']} references unknown segment IDs not found in {transcript_json}: {missing}"
                )
            return [segments_by_id[seg_id] for seg_id in raw_segments]
        return raw_segments

    raise ValueError(f"Clip {clip['id']} is missing 'segment_ids'.")


def ids_are_continuous(segments: list[dict]) -> bool:
    """Check if segment IDs form a perfect sequence with no gaps."""
    if not segments:
        return False
    ids = [s["id"] for s in segments]
    return ids == list(range(ids[0], ids[-1] + 1))


def group_contiguous_segments(segments: list[dict]) -> list[list[dict]]:
    """Group consecutive segment IDs into contiguous ranges to minimize cuts."""
    if not segments:
        return []
    groups = [[segments[0]]]
    for seg in segments[1:]:
        if seg["id"] == groups[-1][-1]["id"] + 1:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    return groups


def run_ffmpeg(cmd: list[str]) -> None:
    """Run an FFmpeg command with captured output so parallel logs don't interleave."""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        error_lines = (result.stderr or "").strip().splitlines()[-10:]
        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr="\n".join(error_lines),
        )


def process_clip(clip: dict, segments_by_id: dict[int, dict], input_video: Path, output_dir: Path) -> Path:
    clip_id = clip["id"]
    title = clip["recommended_title"]
    segments = resolve_clip_segments(clip, segments_by_id)
    if not segments:
        raise ValueError(f"Clip {clip_id} has no segments.")

    final_output = output_dir / f"clip_{clip_id}.mp4"
    groups = group_contiguous_segments(segments)

    log(f"[Clip {clip_id}] Starting: {title}")

    if len(groups) == 1:
        # --- SINGLE CUT (IDs are continuous) ---
        start_time = groups[0][0]["start"]
        end_time = groups[0][-1]["end"]

        log(
            f"[Clip {clip_id}] IDs continuous ({groups[0][0]['id']}–{groups[0][-1]['id']}). "
            f"Single cut: {start_time}s → {end_time}s"
        )

        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(input_video),
            "-c:v", VIDEO_ENCODER,
            *VIDEO_OPTIONS,
            "-c:a", "aac",
            str(final_output)
        ]
        run_ffmpeg(cmd)
    else:
        # --- MULTI-CUT + CONCAT (IDs have gaps) ---
        ranges_str = ", ".join(
            f"{g[0]['id']}–{g[-1]['id']}" if len(g) > 1 else str(g[0]["id"])
            for g in groups
        )
        log(
            f"[Clip {clip_id}] IDs have gaps ({ranges_str}). "
            f"Cutting {len(groups)} contiguous parts and concatenating..."
        )

        temp_files: list[Path] = []
        concat_txt = output_dir / f"concat_{clip_id}.txt"
        try:
            for idx, group in enumerate(groups):
                temp_part = output_dir / f"temp_{clip_id}_{idx}.mp4"
                temp_files.append(temp_part)
                cmd = [
                    "ffmpeg", "-y",
                    "-hide_banner", "-loglevel", "error",
                    "-ss", str(group[0]["start"]),
                    "-to", str(group[-1]["end"]),
                    "-i", str(input_video),
                    "-c:v", VIDEO_ENCODER,
                    *VIDEO_OPTIONS,
                    "-c:a", "aac",
                    str(temp_part)
                ]
                run_ffmpeg(cmd)

            # Write list of parts to concatenate
            with open(concat_txt, "w", encoding="utf-8") as f:
                for tf in temp_files:
                    f.write(f"file '{tf.resolve().as_posix()}'\n")

            # Merge parts into final clip
            concat_cmd = [
                "ffmpeg", "-y",
                "-hide_banner", "-loglevel", "error",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_txt),
                "-c", "copy",
                str(final_output)
            ]
            run_ffmpeg(concat_cmd)
        finally:
            # Always clean up temporary parts
            concat_txt.unlink(missing_ok=True)
            for tf in temp_files:
                tf.unlink(missing_ok=True)

    log(f"[Clip {clip_id}] Created: {final_output}")
    return final_output


# use this when importing
def create_clips(clip_ids=None, max_workers: int | None = None):
    """Automatically makes all the clips included in clips.json in parallel."""
    output_dir.mkdir(exist_ok=True)

    # Read clips from JSON
    with open(clips_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_clips = data["clips"]

    # If IDs provided, select only those clips
    if clip_ids is not None:
        target_ids = set(clip_ids)
        all_clips = [
            clip for clip in all_clips
            if clip["id"] in target_ids
        ]

    if not all_clips:
        print("No matching clips found.")
        return

    # Load transcript segments once if any clip references segment IDs
    needs_transcript = any(
        "segment_ids" in clip
        or (clip.get("segments") and isinstance(clip["segments"][0], int))
        for clip in all_clips
    )
    segments_by_id = load_segments_by_id(transcript_json) if needs_transcript else {}

    workers = max(1, min(max_workers or DEFAULT_MAX_WORKERS, len(all_clips)))
    log(f"Rendering {len(all_clips)} clip(s) using {workers} parallel worker(s) ({VIDEO_ENCODER})...")

    succeeded = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_clip = {
            executor.submit(process_clip, clip, segments_by_id, input_video, output_dir): clip
            for clip in all_clips
        }
        for future in as_completed(future_to_clip):
            clip = future_to_clip[future]
            try:
                future.result()
                succeeded += 1
            except subprocess.CalledProcessError as e:
                failed += 1
                details = f"\n{e.stderr}" if e.stderr else ""
                log(f"[Clip {clip['id']}] FFmpeg error (exit {e.returncode}):{details}")
            except Exception as e:
                failed += 1
                log(f"[Clip {clip['id']}] Error processing clip: {e}")

    log(f"\nDone! Rendered {succeeded}/{len(all_clips)} clips ({failed} failed) in {output_dir}/.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render video clips defined in data/clips.json.")
    parser.add_argument(
        "clip_ids",
        nargs="*",
        type=int,
        help="Optional clip IDs to render (defaults to all clips).",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=None,
        help=f"Number of parallel FFmpeg workers (default: {DEFAULT_MAX_WORKERS}).",
    )
    args = parser.parse_args()

    target_ids = args.clip_ids if args.clip_ids else None
    if target_ids:
        print(f"Processing specific clips: {set(target_ids)}")
    else:
        print("Processing all clips...")

    create_clips(clip_ids=target_ids, max_workers=args.workers)
