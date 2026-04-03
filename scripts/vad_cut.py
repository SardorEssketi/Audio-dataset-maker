#!/usr/bin/env python3
"""
Voice Activity Detection (VAD) based audio segmentation
Splits audio files into smaller segments using WebRTC VAD
"""

import os
from pathlib import Path
from typing import List, Tuple
import yaml
from tqdm import tqdm
import soundfile as sf
import numpy as np
import webrtcvad
import struct
import json


class VADSegmenter:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.input_dir = Path(self.config['paths']['denoised_audio'])
        self.output_dir = Path(self.config['paths']['vad_segments'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.sample_rate = self.config['audio']['sample_rate']
        self.aggressiveness = self.config['vad']['aggressiveness']
        self.frame_duration_ms = self.config['vad']['frame_duration_ms']
        self.padding_duration_ms = self.config['vad']['padding_duration_ms']
        self.min_silence_duration_ms = self.config['vad']['min_silence_duration_ms']
        self.min_segment_duration_s = self.config['vad']['min_segment_duration_s']
        self.max_segment_duration_s = self.config['vad']['max_segment_duration_s']
        
        # Initialize VAD
        self.vad = webrtcvad.Vad(self.aggressiveness)
    
    def frame_generator(self, audio: np.ndarray, sample_rate: int, 
                       frame_duration_ms: int):
        """
        Generate audio frames for VAD processing
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate
            frame_duration_ms: Frame duration in milliseconds
        
        Yields:
            Audio frames as bytes
        """
        n = int(sample_rate * (frame_duration_ms / 1000.0))
        offset = 0
        
        while offset + n <= len(audio):
            frame = audio[offset:offset + n]
            # Convert to 16-bit PCM
            frame_bytes = struct.pack("%dh" % len(frame), 
                                     *np.int16(frame * 32767))
            yield frame_bytes
            offset += n
    
    def vad_collector(self, audio: np.ndarray, sample_rate: int) -> List[Tuple[int, int]]:
        """
        Collect voice segments using VAD
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate
        
        Returns:
            List of (start_sample, end_sample) tuples for voice segments
        """
        num_padding_frames = int(self.padding_duration_ms / self.frame_duration_ms)
        num_silence_frames = int(self.min_silence_duration_ms / self.frame_duration_ms)
        
        ring_buffer = []
        triggered = False
        voiced_frames = []
        segments = []
        
        frame_size = int(sample_rate * (self.frame_duration_ms / 1000.0))
        frame_index = 0
        
        for frame in self.frame_generator(audio, sample_rate, self.frame_duration_ms):
            try:
                is_speech = self.vad.is_speech(frame, sample_rate)
            except:
                # If VAD fails, assume it's speech
                is_speech = True
            
            if not triggered:
                ring_buffer.append((frame_index, is_speech))
                if len(ring_buffer) > num_padding_frames:
                    ring_buffer.pop(0)
                
                num_voiced = len([f for f, speech in ring_buffer if speech])
                if num_voiced > 0.5 * len(ring_buffer):
                    triggered = True
                    # Add frames from ring buffer
                    for f_idx, _ in ring_buffer:
                        voiced_frames.append(f_idx)
                    ring_buffer.clear()
            else:
                voiced_frames.append(frame_index)
                ring_buffer.append((frame_index, is_speech))
                if len(ring_buffer) > num_silence_frames:
                    ring_buffer.pop(0)
                
                num_unvoiced = len([f for f, speech in ring_buffer if not speech])
                if num_unvoiced > 0.9 * len(ring_buffer):
                    triggered = False
                    # Save segment
                    if voiced_frames:
                        start_sample = voiced_frames[0] * frame_size
                        end_sample = min((voiced_frames[-1] + 1) * frame_size, len(audio))
                        segments.append((start_sample, end_sample))
                    voiced_frames.clear()
                    ring_buffer.clear()
            
            frame_index += 1
        
        # Handle any remaining voiced frames
        if voiced_frames:
            start_sample = voiced_frames[0] * frame_size
            end_sample = min((voiced_frames[-1] + 1) * frame_size, len(audio))
            segments.append((start_sample, end_sample))
        
        return segments
    
    def segment_audio_file(self, input_path: str, output_prefix: str = None) -> List[str]:
        """
        Segment an audio file using VAD
        
        Args:
            input_path: Path to input audio file
            output_prefix: Prefix for output files (optional)
        
        Returns:
            List of output file paths
        """
        input_path = Path(input_path)
        
        if output_prefix is None:
            output_prefix = input_path.stem
        
        try:
            # Load audio
            audio, sr = sf.read(input_path)
            
            if sr != self.sample_rate:
                print(f"Warning: Sample rate {sr} != {self.sample_rate}, resampling...")
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
                sr = self.sample_rate
            
            # Get voice segments
            segments = self.vad_collector(audio, sr)
            
            if not segments:
                print(f"No voice segments found in {input_path.name}")
                return []
            
            # Filter and save segments
            output_files = []
            segment_index = 0
            
            for start_sample, end_sample in segments:
                segment = audio[start_sample:end_sample]
                duration = len(segment) / sr
                
                # Check duration constraints
                if duration < self.min_segment_duration_s:
                    continue
                
                # Split long segments
                if duration > self.max_segment_duration_s:
                    # Split into smaller chunks
                    max_samples = int(self.max_segment_duration_s * sr)
                    for i in range(0, len(segment), max_samples):
                        chunk = segment[i:i + max_samples]
                        chunk_duration = len(chunk) / sr
                        
                        if chunk_duration >= self.min_segment_duration_s:
                            output_path = self.output_dir / f"{output_prefix}_seg{segment_index:04d}.wav"
                            sf.write(output_path, chunk, sr, subtype='PCM_16')
                            output_files.append(str(output_path))
                            segment_index += 1
                else:
                    output_path = self.output_dir / f"{output_prefix}_seg{segment_index:04d}.wav"
                    sf.write(output_path, segment, sr, subtype='PCM_16')
                    output_files.append(str(output_path))
                    segment_index += 1
            
            return output_files
        
        except Exception as e:
            print(f"Error segmenting {input_path.name}: {e}")
            return []
    
    def segment_directory(self, input_dir: str = None) -> List[str]:
        """
        Segment all audio files in a directory
        
        Args:
            input_dir: Input directory path (uses config default if None)
        
        Returns:
            List of all output file paths
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
        
        print(f"Found {len(audio_files)} audio files to segment")
        
        all_segments = []
        
        for audio_file in tqdm(audio_files, desc="Segmenting"):
            segments = self.segment_audio_file(audio_file)
            all_segments.extend(segments)
        
        return all_segments
    
    def get_segment_stats(self, segment_files: List[str]) -> dict:
        """Get statistics about segments"""
        if not segment_files:
            return {}
        
        durations = []
        for file in segment_files:
            audio, sr = sf.read(file)
            durations.append(len(audio) / sr)
        
        stats = {
            'total_segments': len(segment_files),
            'total_duration': sum(durations),
            'mean_duration': np.mean(durations),
            'median_duration': np.median(durations),
            'min_duration': min(durations),
            'max_duration': max(durations)
        }
        
        return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Segment audio using VAD")
    parser.add_argument('--input', help='Input directory (uses config default if not specified)')
    parser.add_argument('--output', help='Output directory (uses config default if not specified)')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--stats', action='store_true', help='Show segment statistics')
    
    args = parser.parse_args()
    
    segmenter = VADSegmenter(args.config)
    
    if args.output:
        segmenter.output_dir = Path(args.output)
        segmenter.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Segment files
    segments = segmenter.segment_directory(args.input)
    
    print(f"\nвњ… Created {len(segments)} segments in {segmenter.output_dir}")
    
    # Show statistics
    if args.stats and segments:
        print("\nрџ“Љ Segment statistics:")
        stats = segmenter.get_segment_stats(segments)
        for key, value in stats.items():
            if 'duration' in key:
                print(f"  {key}: {value:.2f}s")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

