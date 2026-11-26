
import argparse
from pathlib import Path

from video_downloader import download_video
from clip_maker import create_clips
from agent import generate_content_from_transcript
from whisper import get_full_transcript


video_path = Path("./videos")


def _run_processing_steps() -> bool:
    """Run transcription, clip selection, and clip rendering. Returns True on success."""
    # 2. Generate transcript
    try:
        print("Getting full transcript...")
        get_full_transcript()
    except Exception as e:
        print("Transcription failed:", e)
        return False

    # 3. Generate clips JSON
    try:
        print("AI video processing...")
        generate_content_from_transcript()
    except Exception as e:
        print("AI processing failed:", e)
        return False

    # 4. Create actual clips
    try:
        print("Processing clips...")
        create_clips()
    except Exception as e:
        print("Clip creation failed:", e)
        return False

    return True


def main(skip_download: bool = False) -> None:
    print("Running SunoCreator!")

    if skip_download:
        existing_video = video_path / "video.mp4"
        if not existing_video.exists():
            print(f"Cannot skip download: {existing_video} does not exist.")
            return
        print(f"Skipping download; using existing video: {existing_video}")
        if _run_processing_steps():
            print("\nYour clips have been generated!")
        return

    while True:

        # Get video URL
        video_url = input(
            "Requesting a video URL:\n"
        ).strip()

        if not video_url:
            print("URL cannot be empty!")
            continue

        # 1. Download video
        try:
            print("Downloading video...")
            download_video(video_url, str(video_path))

        except Exception as e:
            print("Download failed:", e)
            continue

        if not _run_processing_steps():
            continue

        print("\nYour clips have been generated!")

        # Ask whether to process another video
        choice = input(
            "Press Enter to continue, or type 'q' to quit: "
        ).strip().lower()

        if choice == "q":
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SunoCreator video clipping pipeline.")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading and process the existing videos/video.mp4 file.",
    )
    args = parser.parse_args()
    main(skip_download=args.skip_download)
