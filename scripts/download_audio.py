#!/usr/bin/env python3
"""
Download audio from multiple sources:
1. Local files
2. JSON with URLs
3. Hugging Face datasets
4. Direct URLs
"""

import os
import json
import requests
import yt_dlp
from pathlib import Path
from typing import List, Dict, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import yaml
from datasets import load_dataset
from huggingface_hub import hf_hub_download


class AudioDownloader:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.output_dir = Path(self.config['paths']['raw_audio'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = self.config['download']['max_workers']
        self.chunk_size = self.config['download']['chunk_size']
    
    def download_from_url(self, url: str, filename: str = None) -> str:
        """Download audio file from URL"""
        if filename is None:
            filename = url.split('/')[-1]
            if not any(filename.endswith(ext) for ext in ['.wav', '.mp3', '.flac', '.m4a', '.ogg']):
                filename += '.mp3'
        
        output_path = self.output_dir / filename
        
        if output_path.exists():
            print(f"File already exists: {filename}")
            return str(output_path)
        
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
            
            print(f"Downloaded: {filename}")
            return str(output_path)
        
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def _download_youtube_raw(self, url: str, use_ffmpeg: bool) -> List[str]:
        output_template = str(self.output_dir / "%(title)s_%(id)s.%(ext)s")
        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": False,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        if use_ffmpeg:
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        files = []
        if not info:
            return files

        if "entries" in info:
            for entry in info["entries"] or []:
                if not entry:
                    continue
                path = entry.get("_filename") or entry.get("requested_downloads", [{}])[0].get("filepath")
                if path:
                    files.append(path)
        else:
            path = info.get("_filename") or info.get("requested_downloads", [{}])[0].get("filepath")
            if path:
                files.append(path)

        return files

    def download_from_youtube(self, url: str) -> List[str]:
        """Download audio from YouTube video or playlist."""
        try:
            files = self._download_youtube_raw(url, use_ffmpeg=True)
            if files:
                return files
        except Exception as e:
            print(f"FFmpeg postprocess failed, retrying without conversion: {e}")

        try:
            return self._download_youtube_raw(url, use_ffmpeg=False)
        except Exception as e:
            print(f"Error downloading YouTube audio: {e}")
            return []
    
    def download_from_json(self, json_path: str) -> List[str]:
        """Download audio files from JSON with URLs"""
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        urls = []
        if isinstance(data, list):
            urls = data
        elif isinstance(data, dict):
            # Support different JSON structures
            if 'urls' in data:
                urls = data['urls']
            elif 'audio' in data:
                urls = data['audio']
            else:
                urls = list(data.values())
        
        downloaded_files = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for i, url in enumerate(urls):
                if isinstance(url, dict):
                    url_str = url.get('url', url.get('audio_url', ''))
                    filename = url.get('filename', f"audio_{i:05d}.mp3")
                else:
                    url_str = url
                    filename = f"audio_{i:05d}.mp3"
                
                future = executor.submit(self.download_from_url, url_str, filename)
                futures[future] = url_str
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    downloaded_files.append(result)
        
        return downloaded_files
    
    def download_from_huggingface(self, dataset_name: str, split: str = "train", 
                                   audio_column: str = "audio") -> List[str]:
        """Download audio from Hugging Face dataset"""
        print(f"Loading dataset: {dataset_name}")
        
        try:
            dataset = load_dataset(dataset_name, split=split, streaming=False)
        except Exception as e:
            print(f"Error loading dataset: {e}")
            return []
        
        downloaded_files = []
        
        for i, item in enumerate(tqdm(dataset, desc="Downloading from HF")):
            try:
                # Get audio data
                if audio_column in item:
                    audio_data = item[audio_column]
                    
                    # Handle different audio formats
                    if isinstance(audio_data, dict):
                        if 'path' in audio_data:
                            # Local file reference
                            audio_path = audio_data['path']
                        elif 'bytes' in audio_data:
                            # Direct bytes
                            filename = f"hf_audio_{i:05d}.wav"
                            output_path = self.output_dir / filename
                            with open(output_path, 'wb') as f:
                                f.write(audio_data['bytes'])
                            downloaded_files.append(str(output_path))
                            continue
                        elif 'array' in audio_data:
                            # Array format - save directly
                            import soundfile as sf
                            filename = f"hf_audio_{i:05d}.wav"
                            output_path = self.output_dir / filename
                            sr = audio_data.get('sampling_rate', 16000)
                            sf.write(output_path, audio_data['array'], sr)
                            downloaded_files.append(str(output_path))
                            continue
                    else:
                        audio_path = audio_data
                    
                    # Copy file to output directory
                    if os.path.exists(audio_path):
                        import shutil
                        filename = f"hf_audio_{i:05d}" + Path(audio_path).suffix
                        output_path = self.output_dir / filename
                        shutil.copy(audio_path, output_path)
                        downloaded_files.append(str(output_path))
            
            except Exception as e:
                print(f"Error processing item {i}: {e}")
                continue
        
        return downloaded_files
    
    def download_from_local(self, source_dir: str, extensions: List[str] = None) -> List[str]:
        """Copy audio files from local directory"""
        if extensions is None:
            extensions = ['.wav', '.mp3', '.flac', '.m4a', '.ogg']
        
        source_path = Path(source_dir)
        if not source_path.exists():
            print(f"Source directory does not exist: {source_dir}")
            return []
        
        downloaded_files = []
        import shutil
        
        for ext in extensions:
            for audio_file in source_path.rglob(f"*{ext}"):
                try:
                    output_path = self.output_dir / audio_file.name
                    if not output_path.exists():
                        shutil.copy(audio_file, output_path)
                    downloaded_files.append(str(output_path))
                except Exception as e:
                    print(f"Error copying {audio_file}: {e}")
        
        return downloaded_files
    
    def download(self, source: Union[str, List[str]], source_type: str = "auto") -> List[str]:
        """
        Main download method with automatic source type detection
        
        Args:
            source: URL, path, or list of sources
            source_type: 'url', 'youtube', 'json', 'huggingface', 'local', or 'auto'
        
        Returns:
            List of downloaded file paths
        """
        if source_type == "auto":
            # Auto-detect source type
            if isinstance(source, list):
                source_type = "urls"
            elif os.path.isfile(source) and source.endswith('.json'):
                source_type = "json"
            elif os.path.isdir(source):
                source_type = "local"
            elif source.startswith(('http://', 'https://')):
                if "youtube.com" in source.lower() or "youtu.be" in source.lower():
                    source_type = "youtube"
                else:
                    source_type = "url"
            elif '/' in source and not os.path.exists(source):
                source_type = "huggingface"
            else:
                raise ValueError(f"Cannot auto-detect source type for: {source}")
        
        if source_type == "url":
            result = self.download_from_url(source)
            return [result] if result else []
        
        elif source_type == "youtube":
            return self.download_from_youtube(source)
        
        elif source_type == "urls":
            downloaded = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self.download_from_url, url) for url in source]
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        downloaded.append(result)
            return downloaded
        
        elif source_type == "json":
            return self.download_from_json(source)
        
        elif source_type == "huggingface":
            return self.download_from_huggingface(source)
        
        elif source_type == "local":
            return self.download_from_local(source)
        
        else:
            raise ValueError(f"Unknown source type: {source_type}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Download audio from multiple sources")
    parser.add_argument('source', help='Source (URL, JSON path, HF dataset, or local directory)')
    parser.add_argument('--type', choices=['url', 'youtube', 'json', 'huggingface', 'local', 'auto'],
                        default='auto', help='Source type')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    
    args = parser.parse_args()
    
    downloader = AudioDownloader(args.config)
    files = downloader.download(args.source, args.type)
    
    print(f"\nвњ… Downloaded {len(files)} files to {downloader.output_dir}")
    for f in files[:10]:
        print(f"  - {Path(f).name}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")


if __name__ == "__main__":
    main()

