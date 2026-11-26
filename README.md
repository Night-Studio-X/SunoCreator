# SunoCreator

Podcast/video audio transcription using [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper).

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)
- Enough disk space for the Whisper model cache and generated transcript

The current script runs the `base` model on CPU with `int8`. It downloads the model from Hugging Face the first time it runs. An internet connection is needed for that first run. FFmpeg does not need to be installed separately; Faster-Whisper decodes media through PyAV.

## Setup

Clone the repository and enter its directory:

```bash
git clone <repository-url>
cd SunoCreator
```

Create the project environment and install the locked dependencies:

```bash
uv sync
```

## Transcribe a video

Place the input video at `videos/video.mp4`, then run:

```bash
uv run python whisper.py
```

The script prints transcription progress and writes the result to `data/full_transcript.json`. The JSON contains video metadata and timestamped transcript segments, including word timestamps.

To use a different input video, update the path passed to `model.transcribe()` in `whisper.py`. The `filename` value in the output metadata should also be updated to match.

## Optional: install with pip

`requirements.txt` is an exported dependency list. If the team is not using uv, create and activate a virtual environment with Python 3.13+, then run:

```bash
python -m pip install -r requirements.txt
```

The project’s `pyproject.toml` and `uv.lock` are the source of truth for dependencies; regenerate `requirements.txt` after dependency changes:

```bash
uv export --format requirements.txt --output-file requirements.txt
```

Download videos in the videos folder:

```bash
python video_downloader.py [youtube video url]
```
To skip the download and start directly with transcription:

```bash
uv run main.py --skip-download
```

To generate clips with existing clips,json, full_transciption.json and video.mp4:

```bash
uv run clip_maker.py -w [number of worker]
```

Here the [number of worker] are the number of clips that will be processed together, set 1 for the smoothest output.
