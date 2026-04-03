#!/usr/bin/env python3
"""
Normalize audio files to standard format:
- 16kHz sample rate
- Mono channel
- WAV format
- 16-bit PCM
"""

import os
from pathlib import Path
from typing import List
import yaml
from tqdm import tqdm
from pydub import AudioSegment
import soundfile as sf
import librosa
import numpy as np


class AudioNormalizer:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.input_dir = Path(self.config['paths']['raw_audio'])
        self.output_dir = Path(self.config['paths']['normalized_audio'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.target_sr = self.config['audio']['sample_rate']
        self.target_channels = self.config['audio']['channels']
        self.target_format = self.config['audio']['format']
    
    def normalize_file(self, input_path: str, output_path: str = None) -> str:
        """
        Normalize a single audio file
        
        Args:
            input_path: Path to input audio file
            output_path: Path to output file (optional)
        
        Returns:
            Path to normalized file
        """
        input_path = Path(input_path)
        
        if output_path is None:
            output_path = self.output_dir / (input_path.stem + '.wav')
        else:
            output_path = Path(output_path)
        
        if output_path.exists():
            # print(f"Already normalized: {output_path.name}")
            return str(output_path)
        
        try:
            # Load audio using librosa (handles most formats)
            audio, sr = librosa.load(input_path, sr=None, mono=False)
            
            # Convert to mono if needed
            if len(audio.shape) > 1:
                audio = librosa.to_mono(audio)
            
            # Resample to target sample rate
            if sr != self.target_sr:
                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.target_sr)
            
            # Normalize amplitude to [-1, 1]
            if audio.max() > 0:
                audio = audio / np.abs(audio).max()
            
            # Save as WAV
            sf.write(output_path, audio, self.target_sr, subtype='PCM_16')
            
            return str(output_path)
        
        except Exception as e:
            print(f"Error normalizing {input_path.name}: {e}")
            
            # Fallback to pydub
            try:
                audio = AudioSegment.from_file(input_path)
                
                # Convert to mono
                if audio.channels > 1:
                    audio = audio.set_channels(1)
                
                # Set sample rate
                audio = audio.set_frame_rate(self.target_sr)
                
                # Set sample width (16-bit)
                audio = audio.set_sample_width(2)
                
                # Export as WAV
                audio.export(output_path, format='wav')
                
                return str(output_path)
            
            except Exception as e2:
                print(f"Failed to normalize {input_path.name} with fallback: {e2}")
                return None
    
    def normalize_directory(self, input_dir: str = None, 
                           extensions: List[str] = None) -> List[str]:
        """
        Normalize all audio files in a directory
        
        Args:
            input_dir: Input directory path (uses config default if None)
            extensions: List of file extensions to process
        
        Returns:
            List of normalized file paths
        """
        if input_dir is None:
            input_dir = self.input_dir
        else:
            input_dir = Path(input_dir)
        
        if extensions is None:
            extensions = ['.wav', '.mp3', '.flac', '.m4a', '.ogg', '.opus']
        
        # Find all audio files
        audio_files = []
        for ext in extensions:
            audio_files.extend(input_dir.glob(f"*{ext}"))
        
        if not audio_files:
            print(f"No audio files found in {input_dir}")
            return []
        
        print(f"Found {len(audio_files)} audio files to normalize")
        
        normalized_files = []
        
        for audio_file in tqdm(audio_files, desc="Normalizing"):
            result = self.normalize_file(audio_file)
            if result:
                normalized_files.append(result)
        
        return normalized_files
    
    def get_audio_info(self, file_path: str) -> dict:
        """Get information about an audio file"""
        try:
            audio, sr = librosa.load(file_path, sr=None, mono=False)
            
            info = {
                'path': file_path,
                'sample_rate': sr,
                'channels': 1 if len(audio.shape) == 1 else audio.shape[0],
                'duration': len(audio) / sr if len(audio.shape) == 1 else audio.shape[1] / sr,
                'samples': len(audio) if len(audio.shape) == 1 else audio.shape[1]
            }
            
            return info
        
        except Exception as e:
            return {'path': file_path, 'error': str(e)}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Normalize audio files")
    parser.add_argument('--input', help='Input directory (uses config default if not specified)')
    parser.add_argument('--output', help='Output directory (uses config default if not specified)')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--info', action='store_true', help='Show audio info before normalizing')
    
    args = parser.parse_args()
    
    normalizer = AudioNormalizer(args.config)
    
    if args.output:
        normalizer.output_dir = Path(args.output)
        normalizer.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Show info if requested
    if args.info:
        input_dir = Path(args.input) if args.input else normalizer.input_dir
        audio_files = list(input_dir.glob("*.mp3")) + list(input_dir.glob("*.wav"))
        if audio_files:
            print("\nрџ“Љ Sample audio info:")
            info = normalizer.get_audio_info(str(audio_files[0]))
            for key, value in info.items():
                print(f"  {key}: {value}")
            print()
    
    # Normalize files
    files = normalizer.normalize_directory(args.input)
    
    print(f"\nвњ… Normalized {len(files)} files to {normalizer.output_dir}")
    
    # Show sample info
    if files:
        print(f"\nрџ“Љ Output format:")
        info = normalizer.get_audio_info(files[0])
        for key, value in info.items():
            if key != 'path':
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

