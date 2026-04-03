#!/usr/bin/env python3
"""
Push audio dataset to Hugging Face Hub
Uploads audio files and transcriptions as a dataset
"""

import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional
import yaml
from tqdm import tqdm
from datasets import Dataset, Audio, Features, Value
from huggingface_hub import HfApi, create_repo
import soundfile as sf


class HuggingFacePusher:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.audio_dir = Path(self.config['paths']['vad_segments'])
        self.transcription_file = Path(self.config['paths']['transcriptions']) / "transcriptions.jsonl"
        # Keep metadata next to audio chunks for easier manual inspection/push workflow
        self.metadata_jsonl = self.audio_dir / "metadata.jsonl"
        self.metadata_csv = self.audio_dir / "metadata.csv"
        
        self.repo_id = self.config['huggingface']['repo_id']
        self.token = self.config['huggingface'].get('token') or os.getenv('HF_TOKEN')
        self.private = self.config['huggingface']['private']
        
        if not self.token:
            raise ValueError("Hugging Face token not found. Set it in config or HF_TOKEN env variable")
        
        self.api = HfApi(token=self.token)

    def _read_audio_info(self, audio_path: Path) -> Dict:
        """Read lightweight audio metadata without loading full waveform."""
        info = sf.info(str(audio_path))
        duration_sec = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
        return {
            "sample_rate": int(info.samplerate) if info.samplerate else 0,
            "num_frames": int(info.frames),
            "num_channels": int(info.channels),
            "duration_sec": round(duration_sec, 4),
            "subtype": str(info.subtype or ""),
            "format": str(info.format or ""),
        }
    
    def load_transcriptions(self, transcription_file: str = None) -> Dict[str, str]:
        """
        Load transcriptions from JSONL file
        
        Args:
            transcription_file: Path to JSONL file (uses config default if None)
        
        Returns:
            Dictionary mapping file_name to transcription
        """
        if transcription_file is None:
            transcription_file = self.transcription_file
        else:
            transcription_file = Path(transcription_file)
        
        transcriptions = {}
        
        with open(transcription_file, 'r', encoding='utf-8') as f:
            for line in f:
                item = json.loads(line)
                file_name = item['file_name']
                transcription = item.get('transcription', '')
                
                # Skip if error or empty transcription
                if 'error' in item or not transcription:
                    continue
                
                transcriptions[file_name] = transcription
        
        return transcriptions
    
    def create_metadata(self, audio_dir: str = None, transcription_file: str = None) -> List[Dict]:
        """
        Build metadata entries for every valid audio-transcription pair.

        Returns:
            List of metadata dicts.
        """
        if audio_dir is None:
            audio_dir = self.audio_dir
        else:
            audio_dir = Path(audio_dir)

        transcriptions = self.load_transcriptions(transcription_file)
        metadata = []

        for file_name, transcription in tqdm(transcriptions.items(), desc="Building metadata"):
            audio_path = audio_dir / file_name
            if not audio_path.exists():
                continue

            audio_info = self._read_audio_info(audio_path)
            words = transcription.split()

            metadata.append({
                "file_name": file_name,
                "audio_path": str(audio_path),
                "transcription": transcription,
                "num_chars": len(transcription),
                "num_words": len(words),
                **audio_info,
            })

        return metadata

    def save_metadata_files(self, metadata: List[Dict],
                            jsonl_path: str = None,
                            csv_path: str = None) -> Dict[str, str]:
        """Save metadata to JSONL and CSV files."""
        jsonl_file = Path(jsonl_path) if jsonl_path else self.metadata_jsonl
        csv_file = Path(csv_path) if csv_path else self.metadata_csv

        jsonl_file.parent.mkdir(parents=True, exist_ok=True)

        with open(jsonl_file, "w", encoding="utf-8") as f:
            for row in metadata:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        if metadata:
            with open(csv_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(metadata[0].keys()))
                writer.writeheader()
                writer.writerows(metadata)

        return {"jsonl": str(jsonl_file), "csv": str(csv_file)}

    def create_dataset(self, audio_dir: str = None, 
                      transcription_file: str = None) -> Dataset:
        """
        Create Hugging Face dataset from audio files and transcriptions
        
        Args:
            audio_dir: Directory containing audio files
            transcription_file: Path to transcriptions JSONL file
        
        Returns:
            Hugging Face Dataset
        """
        if audio_dir is None:
            audio_dir = self.audio_dir
        else:
            audio_dir = Path(audio_dir)
        
        # Load transcriptions
        print("Loading transcriptions...")
        transcriptions = self.load_transcriptions(transcription_file)
        
        if not transcriptions:
            raise ValueError("No transcriptions found")
        
        print(f"Found {len(transcriptions)} transcriptions")
        
        # Prepare data
        data = []
        missing_audio = []
        
        for file_name, transcription in tqdm(transcriptions.items(), desc="Preparing dataset"):
            audio_path = audio_dir / file_name
            
            if not audio_path.exists():
                missing_audio.append(file_name)
                continue
            
            audio_info = self._read_audio_info(audio_path)
            word_count = len(transcription.split())

            data.append({
                'audio': str(audio_path),
                'transcription': transcription,
                'file_name': file_name,
                'duration_sec': audio_info['duration_sec'],
                'sample_rate': audio_info['sample_rate'],
                'num_channels': audio_info['num_channels'],
                'num_words': word_count,
                'num_chars': len(transcription),
            })
        
        if missing_audio:
            print(f"вљ пёЏ  Warning: {len(missing_audio)} audio files not found")
            if len(missing_audio) <= 10:
                for f in missing_audio:
                    print(f"  - {f}")
        
        if not data:
            raise ValueError("No valid audio-transcription pairs found")
        
        print(f"Creating dataset with {len(data)} samples...")
        
        # Create dataset
        dataset = Dataset.from_list(data)
        
        # Cast audio column to Audio feature
        dataset = dataset.cast_column('audio', Audio(sampling_rate=16000))
        
        return dataset
    
    def push_to_hub(self, dataset: Dataset = None, 
                   repo_id: str = None,
                   private: bool = None,
                   commit_message: str = "Upload audio dataset",
                   metadata_files: Optional[Dict[str, str]] = None) -> str:
        """
        Push dataset to Hugging Face Hub
        
        Args:
            dataset: Hugging Face Dataset (creates from config if None)
            repo_id: Repository ID (uses config default if None)
            private: Whether repo should be private (uses config default if None)
            commit_message: Commit message
        
        Returns:
            URL to the dataset
        """
        if dataset is None:
            dataset = self.create_dataset()
        
        if repo_id is None:
            repo_id = self.repo_id
        
        if private is None:
            private = self.private
        
        # Create repository if it doesn't exist
        print(f"Creating/accessing repository: {repo_id}")
        try:
            create_repo(
                repo_id=repo_id,
                repo_type="dataset",
                private=private,
                token=self.token,
                exist_ok=True
            )
        except Exception as e:
            print(f"Note: {e}")
        
        # Push dataset
        print(f"Pushing dataset to {repo_id}...")
        dataset.push_to_hub(
            repo_id=repo_id,
            token=self.token,
            commit_message=commit_message
        )

        # Upload metadata artifacts
        if metadata_files:
            for local_path in metadata_files.values():
                path_obj = Path(local_path)
                if not path_obj.exists():
                    continue
                target_name = f"metadata/{path_obj.name}"
                print(f"Uploading metadata file: {target_name}")
                self.api.upload_file(
                    path_or_fileobj=str(path_obj),
                    path_in_repo=target_name,
                    repo_id=repo_id,
                    repo_type="dataset",
                    token=self.token,
                    commit_message=f"Add metadata file {path_obj.name}",
                )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        return url
    
    def create_dataset_card(self, dataset: Dataset, output_file: str = "README.md") -> str:
        """Create a dataset card (README.md) for the dataset"""
        
        num_samples = len(dataset)
        
        # Calculate statistics
        total_duration = 0
        transcription_lengths = []
        
        for item in dataset:
            # Duration from audio
            audio_array = item['audio']['array']
            sr = item['audio']['sampling_rate']
            total_duration += len(audio_array) / sr
            
            # Transcription length
            transcription_lengths.append(len(item['transcription']))
        
        avg_duration = total_duration / num_samples
        avg_transcription_length = sum(transcription_lengths) / len(transcription_lengths)
        
        # Create card content
        card_content = f"""---
language:
- ru
task_categories:
- automatic-speech-recognition
size_categories:
- {self._get_size_category(num_samples)}
---

# Audio Dataset

This dataset contains audio recordings with transcriptions.

## Dataset Details

- **Number of samples:** {num_samples}
- **Total duration:** {total_duration / 3600:.2f} hours
- **Average duration per sample:** {avg_duration:.2f} seconds
- **Average transcription length:** {avg_transcription_length:.0f} characters

## Dataset Structure

Each sample contains:
- `audio`: Audio file (16kHz, mono, WAV)
- `transcription`: Text transcription
- `file_name`: Original filename

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("{self.repo_id}")
```

## Processing Pipeline

This dataset was created using an automated pipeline:
1. Audio download from various sources
2. Normalization to 16kHz mono WAV
3. Noise reduction
4. Voice Activity Detection (VAD) segmentation
5. Whisper-based transcription

## License

[Specify your license here]

## Citation

[Add citation information if applicable]
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(card_content)
        
        return output_file
    
    def _get_size_category(self, num_samples: int) -> str:
        """Get size category for dataset card"""
        if num_samples < 1000:
            return "n<1K"
        elif num_samples < 10000:
            return "1K<n<10K"
        elif num_samples < 100000:
            return "10K<n<100K"
        elif num_samples < 1000000:
            return "100K<n<1M"
        else:
            return "n>1M"


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Push audio dataset to Hugging Face")
    parser.add_argument('--audio-dir', help='Audio directory (uses config default if not specified)')
    parser.add_argument('--transcriptions', help='Transcriptions JSONL file (uses config default if not specified)')
    parser.add_argument('--repo-id', help='Hugging Face repo ID (uses config default if not specified)')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--private', action='store_true', help='Make repository private')
    parser.add_argument('--public', action='store_true', help='Make repository public')
    parser.add_argument('--create-card', action='store_true', help='Create dataset card (README.md)')
    parser.add_argument('--preview', action='store_true', help='Preview dataset without pushing')
    
    args = parser.parse_args()
    
    pusher = HuggingFacePusher(args.config)
    
    # Override config with command-line arguments
    if args.repo_id:
        pusher.repo_id = args.repo_id
    if args.private:
        pusher.private = True
    if args.public:
        pusher.private = False
    
    # Create dataset
    dataset = pusher.create_dataset(args.audio_dir, args.transcriptions)
    metadata = pusher.create_metadata(args.audio_dir, args.transcriptions)
    metadata_files = pusher.save_metadata_files(metadata)
    
    print(f"\nрџ“Љ Dataset summary:")
    print(f"  Samples: {len(dataset)}")
    print(f"  Features: {list(dataset.features.keys())}")
    print(f"  Metadata rows: {len(metadata)}")
    print(f"  Metadata JSONL: {metadata_files['jsonl']}")
    print(f"  Metadata CSV: {metadata_files['csv']}")
    
    # Show sample
    print(f"\nрџ“ќ Sample:")
    sample = dataset[0]
    print(f"  file_name: {sample['file_name']}")
    print(f"  transcription: {sample['transcription'][:100]}...")
    
    # Create dataset card if requested
    if args.create_card:
        card_file = pusher.create_dataset_card(dataset)
        print(f"\nрџ“„ Dataset card created: {card_file}")
    
    # Push to hub (unless preview mode)
    if not args.preview:
        url = pusher.push_to_hub(dataset, metadata_files=metadata_files)
        print(f"\nвњ… Dataset pushed successfully!")
        print(f"рџ”— View at: {url}")
    else:
        print(f"\nрџ‘Ђ Preview mode - dataset not pushed")
        print(f"   Run without --preview to push to {pusher.repo_id}")


if __name__ == "__main__":
    main()

