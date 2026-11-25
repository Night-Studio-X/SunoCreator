import os
import sys
import yt_dlp

def download_video(url, output_path='videos', filename='video.mp4'):
    try:
        # Create the output directory if it doesn't exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)
            print(f"Created directory: {output_path}")
        
        print(f"Downloading video from: {url}")
        
        # Configure yt-dlp to download and save as video.mp4
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(output_path, filename),
            'overwrites': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        output_file = os.path.join(output_path, filename)
        if os.path.exists(output_file):
            print(f"\nVideo downloaded successfully and saved as: {output_file}")
        else:
            print(f"\nFile not found at {output_file}. Check if download completed.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1].strip()
    else:
        url = input("Enter the url: ").strip()
        
    if url:
        download_video(url)
    else:
        print("No URL provided.")

