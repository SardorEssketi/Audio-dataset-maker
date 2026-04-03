#!/usr/bin/env python3
"""
Main pipeline orchestrator
"""

import os
import sys
from pathlib import Path
import yaml
import argparse
from typing import Optional, List
import json
import re
import hashlib
import unicodedata

# Add scripts directory to path
script_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(script_dir))


class AudioPipeline:
    """Complete audio processing pipeline"""

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        progress_callback=None,
        job_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        self.config_path = config_path
        self.progress_callback = progress_callback
        self.job_id = job_id
        self.user_id = user_id
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # Lazy imports keep CLI help usable even before full dependency install.
        from download_audio import AudioDownloader
        from normalize import AudioNormalizer
        from noise_reduction import NoiseReducer
        from vad_cut import VADSegmenter
        from whisper import WhisperTranscriber
        from push import HuggingFacePusher
        from filter_transcriptions import TranscriptionFilter

        # Initialize all components
        self.downloader = AudioDownloader(config_path)
        self.normalizer = AudioNormalizer(config_path)
        self.noise_reducer = NoiseReducer(config_path)
        self.segmenter = VADSegmenter(config_path)
        self.transcriber = WhisperTranscriber(config_path)
        self.filterer = TranscriptionFilter(config_path)
        self.pusher = HuggingFacePusher(config_path)

        self.registry_file = Path(self.config["paths"]["transcriptions"]) / "audio_processing_registry.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

        outputs_dir = (
            (self.config.get("paths") or {}).get("outputs")
            or (Path(self.config["paths"]["transcriptions"]).parent / "outputs")
        )
        self.outputs_dir = Path(outputs_dir)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    def emit_progress(self, step, status, progress=0, message=""):
        """Emit progress to callback if available"""
        if self.progress_callback:
            self.progress_callback({
                'step': step,
                'status': status,
                'progress': progress,
                'message': message
            })

    @staticmethod
    def _safe_dir_name(name: str) -> str:
        """
        Make a Windows-safe directory name (keep it readable, avoid reserved characters).
        """
        # Windows reserved characters: <>:"/\|?* plus control chars.
        cleaned = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1F]', "_", str(name))
        cleaned = cleaned.strip(" .")
        return cleaned or "untitled"

    @staticmethod
    def _safe_video_folder_name(name: str) -> str:
        """
        Make a readable, Windows-safe folder name for exported outputs.

        We keep letters (including Cyrillic), digits, and a small set of separators.
        Emoji and other symbol characters are replaced to avoid Windows Explorer ZIP issues.
        """
        s = str(name)
        # Remove characters that are known to cause trouble in Windows Explorer ZIP browsing.
        s = s.replace("\u200d", "")  # ZWJ
        s = s.replace("\ufe0f", "")  # variation selector-16
        s = unicodedata.normalize("NFKC", s)

        out: list[str] = []
        for ch in s:
            if ch in '<>:"/\\|?*':
                out.append("_")
                continue
            cat = unicodedata.category(ch)
            if cat[0] in ("L", "N"):  # letters, numbers (keep Unicode letters)
                out.append(ch)
                continue
            if ch in (" ", "_", "-", ".", "(", ")", "[", "]"):
                out.append("_" if ch == " " else ch)
                continue
            if cat == "Zs":  # other spaces
                out.append("_")
                continue
            # Everything else (including emoji) gets replaced.
            out.append("_")

        cleaned = "".join(out)
        cleaned = re.sub(r"_+", "_", cleaned).strip(" ._-")
        if not cleaned:
            return "untitled"
        # Conservative length cap for filesystem + ZIP consumers.
        if len(cleaned) > 140:
            cleaned = cleaned[:140].rstrip(" ._-")
        return cleaned or "untitled"

    @staticmethod
    def _safe_ascii_slug(name: str) -> str:
        """
        Make a conservative ASCII slug suitable for ZIP/explorer compatibility.
        """
        s = unicodedata.normalize("NFKD", str(name))
        s = s.encode("ascii", "ignore").decode("ascii")
        s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
        s = s.strip(" ._-")
        return s or "untitled"

    def _export_outputs_by_video(
        self,
        transcription_file: Optional[str],
        vad_segments_dir: Optional[str] = None,
    ) -> None:
        """
        Export final artifacts into:
          <outputs>/<video_name>/*.wav
          <outputs>/<video_name>/transcription.json

        Keeps internal normalized/denoised outputs untouched (they are still used by the pipeline).
        """
        if not transcription_file or not os.path.exists(transcription_file):
            return

        src_segments_dir = Path(vad_segments_dir) if vad_segments_dir else self.segmenter.output_dir
        if not src_segments_dir.exists():
            return

        # Some pipelines produce stems like: <video>_seg0000_seg0001.wav
        # We want to group *all* those under <video>, so strip all trailing _seg\d+ chunks.
        seg_suffix_re = re.compile(r"(?:_seg\d+)+$")

        # Group metadata lines by original video stem.
        by_root: dict[str, list[dict]] = {}
        with open(transcription_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                file_name = row.get("file_name") or ""
                if not file_name:
                    continue
                stem = Path(file_name).stem
                root = seg_suffix_re.sub("", stem)
                by_root.setdefault(root, []).append(row)

        if not by_root:
            return

        import shutil

        # Make exports job-specific when invoked from the web backend so downloads can target one job
        # without mixing artifacts across multiple runs for the same user.
        export_root = self.outputs_dir
        if getattr(self, "job_id", None) is not None:
            export_root = self.outputs_dir / "jobs" / f"job_{int(self.job_id)}"
            export_root.mkdir(parents=True, exist_ok=True)

        used_dir_names: set[str] = set()
        for root, rows in by_root.items():
            # Folder name derived from the original file name (stem), but sanitized so
            # Windows Explorer can open the ZIP even for emoji-heavy YouTube titles.
            base_name = self._safe_video_folder_name(root)
            if base_name in used_dir_names:
                base_name = f"{base_name}_{hashlib.sha1(root.encode('utf-8')).hexdigest()[:8]}"
            used_dir_names.add(base_name)

            video_dir = export_root / base_name
            # Ensure the exported video folder contains only the user-facing artifacts.
            if video_dir.exists():
                try:
                    shutil.rmtree(video_dir)
                except Exception:
                    # Best-effort export: never fail the main pipeline.
                    pass
            video_dir.mkdir(parents=True, exist_ok=True)

            # Copy only the segments that exist and are referenced by metadata rows.
            seen_files: set[str] = set()
            exported_rows: list[dict] = []
            for row in rows:
                file_name = row.get("file_name") or ""
                if not file_name or file_name in seen_files:
                    continue
                seen_files.add(file_name)

                src = src_segments_dir / Path(file_name).name
                if not src.exists():
                    continue

                # Rename exported segments to a stable, conflict-free name:
                # - <video>_seg0000.wav               -> seg0000.wav
                # - <video>_seg0000_seg0001.wav       -> seg0000_0001.wav
                stem = Path(file_name).stem
                m2 = re.search(r"_seg(\d+)_seg(\d+)$", stem)
                if m2:
                    a = m2.group(1).zfill(4)
                    b = m2.group(2).zfill(4)
                    exported_name = f"seg{a}_{b}.wav"
                else:
                    m1 = re.search(r"_seg(\d+)$", stem)
                    if m1:
                        exported_name = f"seg{m1.group(1).zfill(4)}.wav"
                    else:
                        exported_name = f"{self._safe_ascii_slug(stem)}.wav"

                # Avoid collisions if inputs are messy.
                candidate = exported_name
                i = 2
                while (video_dir / candidate).exists():
                    stem2 = Path(exported_name).stem
                    ext2 = Path(exported_name).suffix or ".wav"
                    candidate = f"{stem2}_dup{i}{ext2}"
                    i += 1
                exported_name = candidate

                dst = video_dir / exported_name
                if not dst.exists():
                    # Use copy() (not copy2) so the exported files get a fresh mtime.
                    # The download endpoint filters by mtime to approximate job outputs.
                    shutil.copy(src, dst)

                exported_row = dict(row)
                exported_row["file_name"] = exported_name
                exported_row.setdefault("original_file_name", Path(file_name).name)
                exported_rows.append(exported_row)

            # Save a single JSON file with transcriptions next to the audio segments.
            out_json = video_dir / "transcription.json"
            payload = [
                {"file_name": r.get("file_name"), "transcription": r.get("transcription", "")}
                for r in exported_rows
                if r.get("file_name")
            ]
            with open(out_json, "w", encoding="utf-8") as outf:
                json.dump(payload, outf, ensure_ascii=False, indent=2)

    @staticmethod
    def _is_youtube_source(source: str) -> bool:
        lowered = str(source).lower()
        return "youtube.com" in lowered or "youtu.be" in lowered

    def _resolve_registry_source(self, source: str, source_type: str) -> str:
        mapping = {

            "huggingface": "hugging face",
            "json": "json",
            "local": "local",
            "youtube": "youtube",
        }
        if source_type == "auto":
            if os.path.isfile(source) and str(source).lower().endswith(".json"):
                return "json"
            if os.path.isdir(source):
                return "local"
            if self._is_youtube_source(source):
                return "youtube"
            if "/" in str(source) and not os.path.exists(source):
                return "hugging face"
            return "local"
        if source_type == "url":
            return "youtube" if self._is_youtube_source(source) else "local"
        return mapping.get(source_type, "local")

    def _read_registry(self) -> List[dict]:
        if not self.registry_file.exists():
            return []
        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write_registry(self, items: List[dict]):
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def _upsert_registry_items(self, items: List[dict]):
        existing = self._read_registry()
        index = {item.get("name"): i for i, item in enumerate(existing)}
        for item in items:
            name = item.get("name")
            if not name:
                continue
            if name in index:
                existing[index[name]] = item
            else:
                existing.append(item)
        self._write_registry(existing)

    def _update_status_bulk(self, names: List[str], status: str):
        if not names:
            return
        items = self._read_registry()
        names_set = set(names)
        changed = False
        for item in items:
            if item.get("name") in names_set:
                item["status"] = status
                changed = True
        if changed:
            self._write_registry(items)

    def _update_path_bulk_by_stem(self, paths: List[str]):
        if not paths:
            return
        path_by_stem = {Path(p).stem: str(p) for p in paths}
        items = self._read_registry()
        changed = False
        for item in items:
            stem = Path(item.get("name", "")).stem
            if stem in path_by_stem:
                item["path"] = path_by_stem[stem]
                changed = True
        if changed:
            self._write_registry(items)

    def _mark_failed_by_stem_diff(self, expected_paths: List[str], produced_paths: List[str]):
        expected_stems = {Path(p).stem for p in expected_paths}
        produced_stems = {Path(p).stem for p in produced_paths}
        missing = expected_stems - produced_stems
        if not missing:
            return

        items = self._read_registry()
        changed = False
        for item in items:
            name = item.get("name", "")
            stem = Path(name).stem
            if stem in missing:
                item["status"] = "failed"
                changed = True
        if changed:
            self._write_registry(items)

    def _mark_failed_without_segments(self, denoised_files: List[str], segments: List[str]):
        if not denoised_files:
            return
        segment_roots = set()
        for seg in segments:
            seg_stem = Path(seg).stem
            root = re.sub(r"_seg\d+$", "", seg_stem)
            segment_roots.add(root)

        items = self._read_registry()
        denoised_stems = {Path(p).stem for p in denoised_files}
        changed = False
        for item in items:
            stem = Path(item.get("name", "")).stem
            if stem in denoised_stems and stem not in segment_roots:
                item["status"] = "failed"
                changed = True
        if changed:
            self._write_registry(items)

    def _mark_done_from_transcriptions(self, transcription_file: Optional[str]):
        if not transcription_file or not os.path.exists(transcription_file):
            return

        success_roots = set()
        try:
            with open(transcription_file, "r", encoding="utf-8") as f:
                for line in f:
                    row = json.loads(line)
                    if row.get("error"):
                        continue
                    file_name = row.get("file_name", "")
                    if not file_name:
                        continue
                    seg_stem = Path(file_name).stem
                    root = re.sub(r"_seg\d+$", "", seg_stem)
                    if row.get("transcription", "").strip():
                        success_roots.add(root)
        except Exception:
            return

        items = self._read_registry()
        changed = False
        for item in items:
            if item.get("status") == "failed":
                continue
            stem = Path(item.get("name", "")).stem
            if stem in success_roots:
                item["status"] = "done"
                changed = True
        if changed:
            self._write_registry(items)
    
    def run_full_pipeline(self, source: str, source_type: str = "auto",
                         skip_download: bool = False,
                         skip_push: bool = False) -> dict:
        """
        Run the complete pipeline from download to push
        
        Args:
            source: Audio source (URL, directory, etc.)
            source_type: Type of source
            skip_download: Skip download step (use existing files)
            skip_push: Skip push to HuggingFace
        
        Returns:
            Dictionary with results and statistics
        """
        results = {
            'steps': [],
            'errors': []
        }

        try:
            # Step 1: Download (optional)
            if not skip_download:
                self.emit_progress('download', 'running', 0, 'Starting download...')
                print("\n" + "="*60)
                print("STEP 1: Downloading audio files")
                print("="*60)
                downloaded_files = self.downloader.download(source, source_type)
                registry_source = self._resolve_registry_source(source, source_type)
                registry_items = [
                    {
                        "name": Path(file_path).name,
                        "source": registry_source,
                        "status": "pending",
                        "path": str(file_path),
                    }
                    for file_path in downloaded_files
                ]
                self._upsert_registry_items(registry_items)
                self.emit_progress('download', 'completed', 100, f'Downloaded {len(downloaded_files)} files')
                results['steps'].append({
                    'name': 'download',
                    'files_count': len(downloaded_files),
                    'status': 'success'
                })
                print(f"вњ… Downloaded: {len(downloaded_files)} files")
            else:
                print("\nвЏ­пёЏ  Skipping download step")
                # When skipping download, we must already have "raw" audio files available.
                # If the caller provided a directory path, prefer that as the raw input dir.
                input_dir = self.normalizer.input_dir
                try:
                    if isinstance(source, str) and os.path.isdir(source):
                        input_dir = Path(source)
                except Exception:
                    pass

                existing_raw = []
                for ext in [".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus"]:
                    existing_raw.extend(input_dir.glob(f"*{ext}"))
                registry_items = [
                    {
                        "name": p.name,
                        "source": "local",
                        "status": "pending",
                        "path": str(p),
                    }
                    for p in existing_raw
                ]
                self._upsert_registry_items(registry_items)
                downloaded_files = [str(p) for p in existing_raw]

            pending_names = [Path(p).name for p in downloaded_files]
            self._update_status_bulk(pending_names, "processing")

            # Step 2: Normalize
            self.emit_progress('normalize', 'running', 0, 'Normalizing audio...')
            print("\n" + "="*60)
            print("STEP 2: Normalizing audio to 16kHz mono WAV")
            print("="*60)
            # If download was skipped and a custom input dir was provided, normalize from there.
            if skip_download and isinstance(source, str) and os.path.isdir(source):
                normalized_files = self.normalizer.normalize_directory(input_dir=source)
            else:
                normalized_files = self.normalizer.normalize_directory()
            self._update_path_bulk_by_stem(normalized_files)
            self._mark_failed_by_stem_diff(downloaded_files, normalized_files)
            self.emit_progress('normalize', 'completed', 100, f'Normalized {len(normalized_files)} files')
            results['steps'].append({
                'name': 'normalize',
                'files_count': len(normalized_files),
                'status': 'success'
            })
            print(f"вњ… Normalized: {len(normalized_files)} files")

            # Step 3: Noise Reduction
            self.emit_progress('noise_reduction', 'running', 0, 'Reducing noise...')
            print("\n" + "="*60)
            print("STEP 3: Applying noise reduction")
            print("="*60)
            denoised_files = self.noise_reducer.reduce_noise_directory()
            self._update_path_bulk_by_stem(denoised_files)
            self._mark_failed_by_stem_diff(normalized_files, denoised_files)
            self.emit_progress('noise_reduction', 'completed', 100, f'Denoised {len(denoised_files)} files')
            results['steps'].append({
                'name': 'noise_reduction',
                'files_count': len(denoised_files),
                'status': 'success'
            })
            print(f"вњ… Denoised: {len(denoised_files)} files")

            # Step 4: VAD Segmentation
            self.emit_progress('vad_segmentation', 'running', 0, 'Segmenting audio...')
            print("\n" + "="*60)
            print("STEP 4: Segmenting audio with VAD")
            print("="*60)
            segments = self.segmenter.segment_directory()
            self._mark_failed_without_segments(denoised_files, segments)
            self.emit_progress('vad_segmentation', 'completed', 100, f'Created {len(segments)} segments')
            results['steps'].append({
                'name': 'vad_segmentation',
                'segments_count': len(segments),
                'status': 'success'
            })
            print(f"вњ… Created: {len(segments)} segments")

            # Step 5: Whisper Transcription
            self.emit_progress('transcription', 'running', 0, 'Transcribing audio...')
            print("\n" + "="*60)
            print("STEP 5: Transcribing with Whisper")
            print("="*60)
            transcription_file = self.transcriber.transcribe_directory()
            self._mark_done_from_transcriptions(transcription_file)

            stats = self.transcriber.get_transcription_stats(transcription_file)
            self.emit_progress('transcription', 'completed', 100, f'Transcribed {stats.get("transcribed", 0)} files')
            results['steps'].append({
                'name': 'transcription',
                'transcriptions': stats.get('transcribed', 0),
                'status': 'success',
                'stats': stats
            })
            print(f"вњ… Transcribed: {stats.get('transcribed', 0)} files")

            # Step 6: Filter Transcriptions
            self.emit_progress('filter', 'running', 0, 'Filtering transcriptions...')
            print("\n" + "="*60)
            print("STEP 6: Filtering transcriptions")
            print("="*60)
            filter_stats = self.filterer.filter_jsonl()
            self.emit_progress('filter', 'completed', 100, f'Valid: {filter_stats.get("valid", 0)}, Rejected: {filter_stats.get("rejected", 0)}')
            results['steps'].append({
                'name': 'filter',
                'valid': filter_stats.get('valid', 0),
                'rejected': filter_stats.get('rejected', 0),
                'status': 'success',
                'stats': filter_stats
            })
            print(f"вњ… Valid: {filter_stats.get('valid', 0)} files")
            print(f"вќЊ Rejected: {filter_stats.get('rejected', 0)} files")

            # Export final user-facing artifacts:
            # - outputs/<video>/*.wav
            # - outputs/<video>/transcription.json
            export_src = str(getattr(self.filterer, "output_file", "") or "") or transcription_file
            try:
                self._export_outputs_by_video(export_src, vad_segments_dir=str(self.segmenter.output_dir))
            except Exception:
                # Export is best-effort and must not fail the main pipeline.
                pass
            
            # Step 7: Push to HuggingFace (optional)
            if not skip_push:
                print("\n" + "="*60)
                print("STEP 7: Pushing to Hugging Face")
                print("="*60)
                # Use filtered transcriptions
                self.pusher.transcription_file = self.filterer.output_file
                dataset = self.pusher.create_dataset()
                metadata = self.pusher.create_metadata()
                metadata_files = self.pusher.save_metadata_files(metadata)
                url = self.pusher.push_to_hub(dataset, metadata_files=metadata_files)
                results['steps'].append({
                    'name': 'push',
                    'dataset_url': url,
                    'metadata_rows': len(metadata),
                    'metadata_jsonl': metadata_files.get('jsonl'),
                    'metadata_csv': metadata_files.get('csv'),
                    'status': 'success'
                })
                print(f"вњ… Dataset pushed to: {url}")
            else:
                print("\nвЏ­пёЏ  Skipping push to HuggingFace")
            
            results['status'] = 'success'
            return results
        
        except Exception as e:
            self._update_status_bulk(
                [item.get("name") for item in self._read_registry() if item.get("status") == "processing"],
                "failed",
            )
            results['status'] = 'error'
            results['errors'].append(str(e))
            print(f"\nвќЊ Pipeline error: {e}")
            import traceback
            traceback.print_exc()
            return results
    
    def run_partial_pipeline(self, start_step: str, end_step: str) -> dict:
        """
        Run a partial pipeline from start_step to end_step
        
        Steps: download, normalize, denoise, segment, transcribe, push
        """
        steps = ['download', 'normalize', 'denoise', 'segment', 'transcribe', 'push']
        
        if start_step not in steps or end_step not in steps:
            raise ValueError(f"Invalid step. Must be one of: {steps}")
        
        start_idx = steps.index(start_step)
        end_idx = steps.index(end_step)
        
        if start_idx > end_idx:
            raise ValueError("start_step must come before end_step")
        
        # Run appropriate steps
        results = {'steps': [], 'errors': []}
        
        try:
            if 'normalize' in steps[start_idx:end_idx+1]:
                print("\nNormalizing...")
                files = self.normalizer.normalize_directory()
                results['steps'].append({'name': 'normalize', 'files': len(files)})
            
            if 'denoise' in steps[start_idx:end_idx+1]:
                print("\nDenoising...")
                files = self.noise_reducer.reduce_noise_directory()
                results['steps'].append({'name': 'denoise', 'files': len(files)})
            
            if 'segment' in steps[start_idx:end_idx+1]:
                print("\nSegmenting...")
                segments = self.segmenter.segment_directory()
                results['steps'].append({'name': 'segment', 'segments': len(segments)})
            
            if 'transcribe' in steps[start_idx:end_idx+1]:
                print("\nTranscribing...")
                file = self.transcriber.transcribe_directory()
                results['steps'].append({'name': 'transcribe', 'file': file})
            
            if 'push' in steps[start_idx:end_idx+1]:
                print("\nPushing...")
                dataset = self.pusher.create_dataset()
                metadata = self.pusher.create_metadata()
                metadata_files = self.pusher.save_metadata_files(metadata)
                url = self.pusher.push_to_hub(dataset, metadata_files=metadata_files)
                results['steps'].append({
                    'name': 'push',
                    'url': url,
                    'metadata_rows': len(metadata),
                    'metadata_jsonl': metadata_files.get('jsonl'),
                    'metadata_csv': metadata_files.get('csv')
                })
            
            results['status'] = 'success'
            return results
        
        except Exception as e:
            results['status'] = 'error'
            results['errors'].append(str(e))
            return results


def main():
    parser = argparse.ArgumentParser(description="Audio Processing Pipeline")
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    
    # Pipeline options
    parser.add_argument('--source', help='Audio source')
    parser.add_argument('--type', choices=['url', 'youtube', 'json', 'huggingface', 'local', 'auto'],
                       default='auto', help='Source type')
    parser.add_argument('--skip-download', action='store_true', help='Skip download step')
    parser.add_argument('--skip-push', action='store_true', help='Skip push to HF')
    
    # Partial pipeline
    parser.add_argument('--start-step', help='Start from this step')
    parser.add_argument('--end-step', help='End at this step')
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = AudioPipeline(args.config)
    
    # Run pipeline
    if args.source:
        results = pipeline.run_full_pipeline(
            source=args.source,
            source_type=args.type,
            skip_download=args.skip_download,
            skip_push=args.skip_push
        )
        
        print("\n" + "="*60)
        print("PIPELINE COMPLETE")
        print("="*60)
        print(f"Status: {results['status']}")
        print(f"Steps completed: {len(results['steps'])}")
        if results['errors']:
            print(f"Errors: {len(results['errors'])}")
    
    # Run partial pipeline
    elif args.start_step and args.end_step:
        results = pipeline.run_partial_pipeline(args.start_step, args.end_step)
        print(f"\nPartial pipeline complete: {results}")
    
    else:
        parser.print_help()
        print("\nрџ’Ў Tip: Provide --source to run the pipeline")


if __name__ == "__main__":
    main()
