
from video_downloader import download_video
from clip_maker import create_clips
from agent import generate_content_from_transcript
from whisper import get_full_transcript

from pathlib import Path


video_path = Path("./videos")


def main() -> None:
    print("Running SunoCreator!")

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

        # 2. Generate transcript
        try:
            print("Getting full transcript...")
            get_full_transcript()

        except Exception as e:
            print("Transcription failed:", e)
            continue

        # 3. Generate clips JSON
        try:
            print("AI video processing...")
            generate_content_from_transcript()

        except Exception as e:
            print("AI processing failed:", e)
            continue

        # 4. Create actual clips
        try:
            print("Processing clips...")
            create_clips()

        except Exception as e:
            print("Clip creation failed:", e)
            continue

        print("\nYour clips have been generated!")

        # Ask whether to process another video
        choice = input(
            "Press Enter to continue, or type 'q' to quit: "
        ).strip().lower()

        if choice == "q":
            break


if __name__ == "__main__":
    main()
