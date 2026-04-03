#!/usr/bin/env python3
"""
Scheduled scraping runner for all sources.
Supports: youtube/channel/playlist, json lists, huggingface datasets, local folders.
"""

import json
import time
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml
import yt_dlp

from download_audio import AudioDownloader


@dataclass
class SourceResult:
    name: str
    new_files: List[str]
    skipped: int
    errors: List[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_config(config_path: str) -> Dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_registry(registry_path: Path) -> Dict:
    if not registry_path.exists():
        return {
            "items": {},
            "last_run": None,
            "last_summary": None,
            "current": None,
            "recent": [],
            "last_pipeline": None,
        }
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {
                "items": {},
                "last_run": None,
                "last_summary": None,
                "current": None,
                "recent": [],
                "last_pipeline": None,
            }
        data.setdefault("items", {})
        data.setdefault("last_run", None)
        data.setdefault("last_summary", None)
        data.setdefault("current", None)
        data.setdefault("recent", [])
        data.setdefault("last_pipeline", None)
        return data
    except Exception:
        return {
            "items": {},
            "last_run": None,
            "last_summary": None,
            "current": None,
            "recent": [],
            "last_pipeline": None,
        }


def _save_registry(registry_path: Path, registry: Dict):
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def _registry_key(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"


class YouTubeScraper:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def _extract_entries(self, url: str) -> List[Dict]:
        options = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            return []
        if "entries" in info:
            return [e for e in (info["entries"] or []) if e]
        return [info]

    def _passes_filters(self, entry: Dict, filters: Dict) -> bool:
        title = (entry.get("title") or "").lower()
        uploader = (entry.get("uploader") or "").lower()
        description = (entry.get("description") or "").lower()
        text = " ".join([title, uploader, description])

        include = [k.lower() for k in filters.get("include_keywords", []) or []]
        exclude = [k.lower() for k in filters.get("exclude_keywords", []) or []]

        if include and not any(k in text for k in include):
            return False
        if exclude and any(k in text for k in exclude):
            return False

        allow_shorts = bool(filters.get("allow_shorts", False))
        duration = entry.get("duration")
        if duration is not None:
            if not allow_shorts and duration <= 60:
                return False
            min_d = int(filters.get("min_duration_sec", 0) or 0)
            max_d = int(filters.get("max_duration_sec", 0) or 0)
            if min_d and duration < min_d:
                return False
            if max_d and duration > max_d:
                return False

        date_from = (filters.get("upload_date_from") or "").strip()
        date_to = (filters.get("upload_date_to") or "").strip()
        upload_date = entry.get("upload_date")
        if upload_date:
            if date_from and upload_date < date_from.replace("-", ""):
                return False
            if date_to and upload_date > date_to.replace("-", ""):
                return False

        return True

    def list_video_urls(self, url: str, filters: Dict) -> List[str]:
        entries = self._extract_entries(url)
        max_videos = int(filters.get("max_videos", 0) or 0)
        urls: List[str] = []
        for entry in entries:
            if not self._passes_filters(entry, filters):
                continue
            video_id = entry.get("id")
            if video_id:
                urls.append(f"https://www.youtube.com/watch?v={video_id}")
            elif entry.get("url"):
                urls.append(entry.get("url"))
            if max_videos and len(urls) >= max_videos:
                break
        return urls


class ScrapeRunner:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = _load_config(config_path)
        self.downloader = AudioDownloader(config_path)
        self.scrape_cfg = (self.config.get("download") or {}).get("scrape", {})
        self.registry_path = Path(self.scrape_cfg.get("registry_path", "data/scrape_registry.json"))
        self.registry = _load_registry(self.registry_path)
        self.yt = YouTubeScraper(self.downloader.output_dir)

    def _set_current(self, info: Optional[Dict]):
        self.registry["current"] = info
        _save_registry(self.registry_path, self.registry)

    def _add_recent(self, info: Dict):
        recent = self.registry.get("recent", []) or []
        recent.append(info)
        if len(recent) > 20:
            recent = recent[-20:]
        self.registry["recent"] = recent
        _save_registry(self.registry_path, self.registry)

    def _run_pipeline_if_enabled(self, total_new: int, new_files: Optional[List[str]] = None):
        pipeline_cfg = (self.scrape_cfg.get("pipeline") or {}) if self.scrape_cfg else {}
        if not pipeline_cfg.get("enabled", False):
            return
        if total_new <= 0:
            return

        source = pipeline_cfg.get("source", "data/raw")
        source_type = pipeline_cfg.get("type", "local")
        skip_push = bool(pipeline_cfg.get("skip_push", True))

        new_files = new_files or []
        entry = {
            "started_at": _utc_now(),
            "ended_at": None,
            "status": "running",
            "error": None,
            "new_files": total_new,
            "files": new_files,
            "source": source,
            "type": source_type,
            "skip_push": skip_push,
        }
        self.registry["last_pipeline"] = entry
        _save_registry(self.registry_path, self.registry)

        try:
            root_dir = Path(__file__).resolve().parents[1]
            if str(root_dir) not in sys.path:
                sys.path.insert(0, str(root_dir))
            from main import AudioPipeline

            pipeline = AudioPipeline(self.config_path)
            result = pipeline.run_full_pipeline(
                source=source,
                source_type=source_type,
                skip_download=True,
                skip_push=skip_push,
            )
            entry["status"] = result.get("status", "unknown")
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
        finally:
            entry["ended_at"] = _utc_now()
            self.registry["last_pipeline"] = entry
            _save_registry(self.registry_path, self.registry)
            if entry["status"] == "success":
                if total_new == 1 and new_files:
                    print(f"PIPELINE SUCCESS: {Path(new_files[0]).name}")
                else:
                    print(f"PIPELINE SUCCESS: {total_new} files")

    def _should_skip(self, key: str) -> bool:
        return key in self.registry.get("items", {})

    def _mark_done(self, key: str, meta: Optional[Dict] = None):
        self.registry.setdefault("items", {})
        self.registry["items"][key] = {
            "timestamp": _utc_now(),
            "meta": meta or {},
        }

    def _download_urls(self, urls: Iterable[str], name: str) -> SourceResult:
        new_files: List[str] = []
        skipped = 0
        errors: List[str] = []
        for url in urls:
            self._set_current({"source": name, "type": "url", "item": url, "timestamp": _utc_now()})
            print(f"Downloading URL: {url}", flush=True)
            key = _registry_key("url", url)
            if self._should_skip(key):
                skipped += 1
                continue
            path = self.downloader.download_from_url(url)
            if path:
                new_files.append(path)
                self._mark_done(key, {"source": name})
                self._add_recent({"source": name, "type": "url", "item": url, "timestamp": _utc_now()})
            else:
                errors.append(f"Failed url: {url}")
                self._add_recent({"source": name, "type": "url", "item": url, "timestamp": _utc_now(), "error": True})
        return SourceResult(name=name, new_files=new_files, skipped=skipped, errors=errors)

    def _run_json(self, source: Dict) -> SourceResult:
        name = source.get("name", "json")
        path = source.get("path", "")
        if not path:
            return SourceResult(name=name, new_files=[], skipped=0, errors=["Missing json path"])

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        urls = []
        if isinstance(data, list):
            urls = data
        elif isinstance(data, dict):
            if "urls" in data:
                urls = data["urls"]
            elif "audio" in data:
                urls = data["audio"]
            else:
                urls = list(data.values())

        normalized: List[str] = []
        for i, item in enumerate(urls):
            if isinstance(item, dict):
                url_str = item.get("url", item.get("audio_url", ""))
                if url_str:
                    normalized.append(url_str)
            elif isinstance(item, str):
                normalized.append(item)
            else:
                continue

        return self._download_urls(normalized, name)

    def _run_local(self, source: Dict) -> SourceResult:
        name = source.get("name", "local")
        path = source.get("path", "")
        if not path:
            return SourceResult(name=name, new_files=[], skipped=0, errors=["Missing local path"])

        source_path = Path(path)
        if not source_path.exists():
            return SourceResult(name=name, new_files=[], skipped=0, errors=[f"Path not found: {path}"])

        exts = [".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus"]
        new_files: List[str] = []
        skipped = 0
        errors: List[str] = []

        import shutil

        for ext in exts:
            for audio_file in source_path.rglob(f"*{ext}"):
                self._set_current({"source": name, "type": "local", "item": str(audio_file), "timestamp": _utc_now()})
                print(f"Copying local: {audio_file}", flush=True)
                key = _registry_key("local", f"{audio_file}:{audio_file.stat().st_mtime}")
                if self._should_skip(key):
                    skipped += 1
                    continue
                try:
                    output_path = self.downloader.output_dir / audio_file.name
                    if not output_path.exists():
                        shutil.copy(audio_file, output_path)
                    new_files.append(str(output_path))
                    self._mark_done(key, {"source": name, "file": str(audio_file)})
                    self._add_recent({"source": name, "type": "local", "item": str(audio_file), "timestamp": _utc_now()})
                except Exception as e:
                    errors.append(f"Failed local {audio_file}: {e}")
                    self._add_recent({"source": name, "type": "local", "item": str(audio_file), "timestamp": _utc_now(), "error": True})

        return SourceResult(name=name, new_files=new_files, skipped=skipped, errors=errors)

    def _run_huggingface(self, source: Dict) -> SourceResult:
        name = source.get("name", "huggingface")
        dataset = source.get("dataset", "")
        if not dataset:
            return SourceResult(name=name, new_files=[], skipped=0, errors=["Missing dataset"])

        split = source.get("split", "train")
        audio_column = source.get("audio_column", "audio")
        max_items = int(source.get("max_items", 0) or 0)

        try:
            from datasets import load_dataset
        except Exception as e:
            return SourceResult(name=name, new_files=[], skipped=0, errors=[str(e)])

        try:
            dataset_obj = load_dataset(dataset, split=split, streaming=False)
        except Exception as e:
            return SourceResult(name=name, new_files=[], skipped=0, errors=[str(e)])

        new_files: List[str] = []
        skipped = 0
        errors: List[str] = []
        for i, item in enumerate(dataset_obj):
            if max_items and len(new_files) >= max_items:
                break
            self._set_current({"source": name, "type": "huggingface", "item": f"{dataset}:{split}:{i}", "timestamp": _utc_now()})
            print(f"Downloading HF item: {dataset}:{split}:{i}", flush=True)
            key = _registry_key("hf", f"{dataset}:{split}:{i}")
            if self._should_skip(key):
                skipped += 1
                continue

            audio_data = item.get(audio_column)
            if not audio_data:
                skipped += 1
                continue

            try:
                if isinstance(audio_data, dict) and "bytes" in audio_data:
                    filename = f"hf_audio_{i:05d}.wav"
                    output_path = self.downloader.output_dir / filename
                    with open(output_path, "wb") as f:
                        f.write(audio_data["bytes"])
                    new_files.append(str(output_path))
                    self._mark_done(key, {"source": name})
                    self._add_recent({"source": name, "type": "huggingface", "item": f"{dataset}:{split}:{i}", "timestamp": _utc_now()})
                    continue

                if isinstance(audio_data, dict) and "array" in audio_data:
                    import soundfile as sf
                    filename = f"hf_audio_{i:05d}.wav"
                    output_path = self.downloader.output_dir / filename
                    sr = audio_data.get("sampling_rate", 16000)
                    sf.write(output_path, audio_data["array"], sr)
                    new_files.append(str(output_path))
                    self._mark_done(key, {"source": name})
                    self._add_recent({"source": name, "type": "huggingface", "item": f"{dataset}:{split}:{i}", "timestamp": _utc_now()})
                    continue

                if isinstance(audio_data, dict) and "path" in audio_data:
                    audio_path = Path(audio_data["path"])
                else:
                    audio_path = Path(audio_data)

                if audio_path.exists():
                    import shutil
                    filename = f"hf_audio_{i:05d}" + audio_path.suffix
                    output_path = self.downloader.output_dir / filename
                    shutil.copy(audio_path, output_path)
                    new_files.append(str(output_path))
                    self._mark_done(key, {"source": name})
                    self._add_recent({"source": name, "type": "huggingface", "item": f"{dataset}:{split}:{i}", "timestamp": _utc_now()})
            except Exception as e:
                errors.append(f"HF item {i}: {e}")
                self._add_recent({"source": name, "type": "huggingface", "item": f"{dataset}:{split}:{i}", "timestamp": _utc_now(), "error": True})

        return SourceResult(name=name, new_files=new_files, skipped=skipped, errors=errors)

    def _run_youtube(self, source: Dict) -> SourceResult:
        name = source.get("name", "youtube")
        url = source.get("url", "")
        if not url:
            return SourceResult(name=name, new_files=[], skipped=0, errors=["Missing youtube url"])

        urls = self.yt.list_video_urls(url, source)
        new_files: List[str] = []
        skipped = 0
        errors: List[str] = []

        for video_url in urls:
            self._set_current({"source": name, "type": "youtube", "item": video_url, "timestamp": _utc_now()})
            print(f"Downloading YouTube: {video_url}", flush=True)
            key = _registry_key("yt", video_url)
            if self._should_skip(key):
                skipped += 1
                continue
            try:
                files = self.downloader.download_from_youtube(video_url)
                if files:
                    new_files.extend(files)
                    self._mark_done(key, {"source": name})
                    self._add_recent({"source": name, "type": "youtube", "item": video_url, "timestamp": _utc_now()})
                else:
                    errors.append(f"Failed youtube: {video_url}")
                    self._add_recent({"source": name, "type": "youtube", "item": video_url, "timestamp": _utc_now(), "error": True})
            except Exception as e:
                errors.append(f"YouTube error {video_url}: {e}")
                self._add_recent({"source": name, "type": "youtube", "item": video_url, "timestamp": _utc_now(), "error": True})

        return SourceResult(name=name, new_files=new_files, skipped=skipped, errors=errors)

    def run_once(self) -> List[SourceResult]:
        results: List[SourceResult] = []
        sources = self.scrape_cfg.get("sources", []) or []
        for source in sources:
            src_type = (source.get("type") or "").lower()
            if src_type == "youtube":
                results.append(self._run_youtube(source))
            elif src_type == "json":
                results.append(self._run_json(source))
            elif src_type == "huggingface":
                results.append(self._run_huggingface(source))
            elif src_type == "local":
                results.append(self._run_local(source))
            else:
                results.append(SourceResult(name=source.get("name", src_type or "unknown"), new_files=[], skipped=0, errors=[f"Unknown type: {src_type}"]))

        self.registry["last_run"] = _utc_now()
        summary = {
            "total_new": sum(len(r.new_files) for r in results),
            "total_skipped": sum(r.skipped for r in results),
            "total_errors": sum(len(r.errors) for r in results),
            "sources": [
                {
                    "name": r.name,
                    "new": len(r.new_files),
                    "skipped": r.skipped,
                    "errors": len(r.errors),
                }
                for r in results
            ],
        }
        self.registry["last_summary"] = summary
        self._set_current(None)
        _save_registry(self.registry_path, self.registry)
        all_new_files: List[str] = []
        for r in results:
            all_new_files.extend(r.new_files)
        self._run_pipeline_if_enabled(summary.get("total_new", 0), all_new_files)
        return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scheduled scraping runner")
    parser.add_argument("--config", default="config/config.yaml", help="Config file path")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval-minutes", type=int, help="Override interval minutes")

    args = parser.parse_args()

    runner = ScrapeRunner(args.config)
    cfg = runner.scrape_cfg
    enabled = bool(cfg.get("enabled", False))
    interval = int(args.interval_minutes or cfg.get("interval_minutes", 180) or 180)

    if not enabled and not args.once:
        print("Scrape runner is disabled. Set download.scrape.enabled=true or use --once")
        return

    while True:
        results = runner.run_once()
        total_new = sum(len(r.new_files) for r in results)
        total_skipped = sum(r.skipped for r in results)
        total_errors = sum(len(r.errors) for r in results)

        print("\nScrape summary:")
        for r in results:
            print(f"- {r.name}: +{len(r.new_files)} new, {r.skipped} skipped, {len(r.errors)} errors")
            for err in r.errors[:5]:
                print(f"  ! {err}")

        print(f"Total new: {total_new}; skipped: {total_skipped}; errors: {total_errors}")

        if args.once:
            break

        print(f"Sleeping for {interval} minutes...")
        time.sleep(interval * 60)


if __name__ == "__main__":
    main()
