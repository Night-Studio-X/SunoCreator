import os
import yt_dlp
import sys

def download_video(url, output_path='videos', filename='video.mp4'):
    try:
        # Create the output directory if it doesn't exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)
            print(f"Created directory: {output_path}")
        
        print(f"Downloading video from: {url}")
        
        # Configure yt-dlp
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(output_path, filename), 
            'quiet': False,
            'verbose': True,
            'no_warnings': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            print(f"Downloaded video info: {info_dict}")
        
        output_file = os.path.join(output_path, filename)
        if os.path.exists(output_file):
            print(f"Video downloaded successfully and saved as: {output_file}")
        else:
            print(f"File not found at {output_file}. Check if the download was successful.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        url = input("Enter the YouTube URL: ")
    else:
        url = sys.argv[1]
    download_video(url)
