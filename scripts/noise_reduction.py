#!/usr/bin/env python3
"""
Noise reduction for audio files using noisereduce library
"""

import os
from pathlib import Path
from typing import List
import yaml
from tqdm import tqdm
import soundfile as sf
import numpy as np
import noisereduce as nr


class NoiseReducer:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.input_dir = Path(self.config['paths']['normalized_audio'])
        self.output_dir = Path(self.config['paths']['denoised_audio'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.enabled = self.config['noise_reduction']['enabled']
        self.stationary = self.config['noise_reduction']['stationary']
        self.prop_decrease = self.config['noise_reduction']['prop_decrease']
        self.sample_rate = self.config['audio']['sample_rate']
    
    def reduce_noise_file(self, input_path: str, output_path: str = None) -> str:
        """
        Apply noise reduction to a single audio file
        
        Args:
            input_path: Path to input audio file
            output_path: Path to output file (optional)
        
        Returns:
            Path to denoised file
        """
        if not self.enabled:
            # If noise reduction is disabled, just copy the file
            import shutil
            input_path = Path(input_path)
            if output_path is None:
                output_path = self.output_dir / input_path.name
            else:
                output_path = Path(output_path)
            shutil.copy(input_path, output_path)
            return str(output_path)
        
        input_path = Path(input_path)
        
        if output_path is None:
            output_path = self.output_dir / input_path.name
        else:
            output_path = Path(output_path)
        
        if output_path.exists():
            # print(f"Already denoised: {output_path.name}")
            return str(output_path)
        
        try:
            # Load audio
            audio, sr = sf.read(input_path)
            
            # Apply noise reduction
            # Using stationary noise reduction (works well for constant background noise)
            reduced_audio = nr.reduce_noise(
                y=audio,
                sr=sr,
                stationary=self.stationary,
                prop_decrease=self.prop_decrease
            )
            
            # Normalize to prevent clipping
            if np.abs(reduced_audio).max() > 0:
                reduced_audio = reduced_audio / np.abs(reduced_audio).max() * 0.95
            
            # Save denoised audio
            sf.write(output_path, reduced_audio, sr, subtype='PCM_16')
            
            return str(output_path)
        
        except Exception as e:
            print(f"Error reducing noise in {input_path.name}: {e}")
            return None
    
    def reduce_noise_directory(self, input_dir: str = None) -> List[str]:
        """
        Apply noise reduction to all audio files in a directory
        
        Args:
            input_dir: Input directory path (uses config default if None)
        
        Returns:
            List of denoised file paths
        """
        if input_dir is None:
            input_dir = self.input_dir
        else:
            input_dir = Path(input_dir)
        
        # Find all WAV files
        audio_files = list(input_dir.glob("*.wav"))
        
        if not audio_files:
            print(f"No WAV files found in {input_dir}")
            return []
        
        print(f"Found {len(audio_files)} audio files for noise reduction")
        
        if not self.enabled:
            print("вљ пёЏ  Noise reduction is disabled in config - files will be copied as-is")
        
        denoised_files = []
        
        for audio_file in tqdm(audio_files, desc="Reducing noise"):
            result = self.reduce_noise_file(audio_file)
            if result:
                denoised_files.append(result)
        
        return denoised_files
    
    def analyze_noise(self, file_path: str, duration: float = 1.0) -> dict:
        """
        Analyze noise profile of an audio file
        Uses the first 'duration' seconds to estimate noise
        
        Args:
            file_path: Path to audio file
            duration: Duration in seconds to analyze
        
        Returns:
            Dictionary with noise statistics
        """
        try:
            audio, sr = sf.read(file_path)
            
            # Get the first 'duration' seconds
            samples = int(duration * sr)
            if len(audio) < samples:
                noise_sample = audio
            else:
                noise_sample = audio[:samples]
            
            stats = {
                'mean': float(np.mean(noise_sample)),
                'std': float(np.std(noise_sample)),
                'max': float(np.max(np.abs(noise_sample))),
                'rms': float(np.sqrt(np.mean(noise_sample**2))),
                'duration_analyzed': len(noise_sample) / sr
            }
            
            return stats
        
        except Exception as e:
            return {'error': str(e)}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply noise reduction to audio files")
    parser.add_argument('--input', help='Input directory (uses config default if not specified)')
    parser.add_argument('--output', help='Output directory (uses config default if not specified)')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--analyze', action='store_true', help='Analyze noise before processing')
    parser.add_argument('--disable', action='store_true', help='Disable noise reduction (just copy files)')
    
    args = parser.parse_args()
    
    reducer = NoiseReducer(args.config)
    
    if args.disable:
        reducer.enabled = False
    
    if args.output:
        reducer.output_dir = Path(args.output)
        reducer.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Analyze noise if requested
    if args.analyze:
        input_dir = Path(args.input) if args.input else reducer.input_dir
        audio_files = list(input_dir.glob("*.wav"))
        if audio_files:
            print("\nрџ“Љ Noise analysis (first file):")
            stats = reducer.analyze_noise(str(audio_files[0]))
            for key, value in stats.items():
                print(f"  {key}: {value}")
            print()
    
    # Process files
    files = reducer.reduce_noise_directory(args.input)
    
    status = "вњ…" if reducer.enabled else "рџ“‹"
    action = "Denoised" if reducer.enabled else "Copied"
    print(f"\n{status} {action} {len(files)} files to {reducer.output_dir}")


if __name__ == "__main__":
    main()

