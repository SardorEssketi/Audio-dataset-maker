#!/usr/bin/env python3
"""
Transcribe audio segments with a single fixed Whisper model:
OvozifyLabs/whisper-small-uz-v1

Supports two backends:
1) local (GPU/CPU)
2) server (custom HTTP endpoint)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import requests
import torch
import yaml
from tqdm import tqdm


class WhisperTranscriber:
    REQUIRED_MODEL = "OvozifyLabs/whisper-small-uz-v1"

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.input_dir = Path(self.config["paths"]["vad_segments"])
        self.output_dir = Path(self.config["paths"]["transcriptions"])
        self.output_dir.mkdir(parents=True, exist_ok=True)

        whisper_cfg = self.config.get("whisper", {})

        configured_model = whisper_cfg.get("model_name", self.REQUIRED_MODEL)
        if configured_model != self.REQUIRED_MODEL:
            print(
                f"Warning: model '{configured_model}' is ignored. "
                f"Using fixed model '{self.REQUIRED_MODEL}'."
            )
        self.model_name = self.REQUIRED_MODEL

        self.batch_size = int(whisper_cfg.get("batch_size", 8))
        self.language = whisper_cfg.get("language", "uz")
        self.compute_type = whisper_cfg.get("compute_type", "float16")

        self.mode = whisper_cfg.get("mode", "auto")  # auto/local/server
        self.device_preference = whisper_cfg.get("device", "cuda")  # cuda/cpu

        server_cfg = whisper_cfg.get("server", {})
        self.server_url = server_cfg.get("url", "").strip()
        self.server_api_key_env = server_cfg.get("api_key_env", "WHISPER_SERVER_API_KEY")
        self.server_timeout = int(server_cfg.get("timeout_sec", 180))
        self.server_file_field = server_cfg.get("file_field", "file")
        self.server_text_field = server_cfg.get("response_text_field", "text")

        self.use_server = False
        self.device: Optional[str] = None

        self.pipe = None
        self.model = None
        self.processor = None

        self._determine_mode()

    def _determine_mode(self):
        """Resolve runtime mode and device."""
        if self.mode == "server":
            if not self.server_url:
                raise ValueError("whisper.mode=server but whisper.server.url is empty")
            self.use_server = True
            self.device = None
            print(f"Mode: server ({self.server_url})")
            return

        if self.mode == "local":
            self.use_server = False
            if self.device_preference == "cuda" and torch.cuda.is_available():
                self.device = "cuda"
                print(f"Mode: local GPU ({torch.cuda.get_device_name(0)})")
            else:
                self.device = "cpu"
                print("Mode: local CPU")
            return

        # auto
        self.use_server = False
        if self.device_preference == "cuda" and torch.cuda.is_available():
            self.device = "cuda"
            print(f"Mode: auto -> local GPU ({torch.cuda.get_device_name(0)})")
        else:
            self.device = "cpu"
            print("Mode: auto -> local CPU")

    def configure_runtime(
        self,
        mode: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
        language: Optional[str] = None,
        compute_type: Optional[str] = None,
        server_url: Optional[str] = None,
    ):
        """Override runtime settings without editing config file."""
        if mode:
            self.mode = mode
        if device:
            self.device_preference = device
        if batch_size is not None:
            self.batch_size = int(batch_size)
        if language:
            self.language = language
        if compute_type:
            self.compute_type = compute_type
        if server_url is not None:
            self.server_url = server_url.strip()

        # Model/device/pipeline may need re-init if settings changed
        self.pipe = None
        self.model = None
        self.processor = None

        self._determine_mode()

    def load_model(self):
        """Load local Whisper model for local mode."""
        if self.use_server:
            return

        if self.pipe is not None:
            return

        print(f"Loading Whisper model: {self.model_name}")
        print(f"Device: {self.device}")

        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        torch_dtype = (
            torch.float16
            if self.compute_type == "float16" and self.device == "cuda"
            else torch.float32
        )

        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_name,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )
        self.model.to(self.device)

        self.processor = AutoProcessor.from_pretrained(self.model_name)

        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            torch_dtype=torch_dtype,
            device=self.device,
        )

        print("Local Whisper model loaded successfully")

    def _extract_server_text(self, payload: Dict) -> str:
        value = payload
        for key in self.server_text_field.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                raise KeyError(
                    f"response_text_field='{self.server_text_field}' not found in server response"
                )
        return value if isinstance(value, str) else str(value)

    def _transcribe_via_server(self, audio_path: str) -> str:
        api_key = Path  # noop to keep linters quiet when env key is empty
        del api_key

        headers = {}
        token = ""
        if self.server_api_key_env:
            import os

            token = os.getenv(self.server_api_key_env, "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with open(audio_path, "rb") as f:
            files = {self.server_file_field: (Path(audio_path).name, f, "audio/wav")}
            data = {"model": self.model_name, "language": self.language}
            resp = requests.post(
                self.server_url,
                headers=headers,
                data=data,
                files=files,
                timeout=self.server_timeout,
            )

        resp.raise_for_status()
        payload = resp.json()
        return self._extract_server_text(payload).strip()

    def transcribe_file(self, audio_path: str) -> Dict[str, str]:
        """Transcribe a single file."""
        file_name = Path(audio_path).name
        try:
            if self.use_server:
                text = self._transcribe_via_server(audio_path)
                return {"file_name": file_name, "transcription": text}

            if self.pipe is None:
                self.load_model()

            generate_kwargs = {}
            if self.language != "auto":
                generate_kwargs["language"] = self.language

            result = self.pipe(
                audio_path,
                generate_kwargs=generate_kwargs,
                return_timestamps=False,
            )
            return {"file_name": file_name, "transcription": result["text"].strip()}
        except Exception as e:
            return {"file_name": file_name, "transcription": "", "error": str(e)}

    def transcribe_batch(self, audio_paths: List[str]) -> List[Dict[str, str]]:
        return [self.transcribe_file(path) for path in audio_paths]

    def transcribe_directory(
        self, input_dir: Optional[str] = None, output_file: Optional[str] = None
    ) -> Optional[str]:
        if input_dir is None:
            wav_dir = self.input_dir
        else:
            wav_dir = Path(input_dir)

        out_path = (
            self.output_dir / "transcriptions.jsonl"
            if output_file is None
            else Path(output_file)
        )

        audio_files = sorted(list(wav_dir.glob("*.wav")))
        if not audio_files:
            print(f"No WAV files found in {wav_dir}")
            return None

        print(f"Found {len(audio_files)} audio files to transcribe")
        mode_label = "server" if self.use_server else f"local-{self.device}"
        print(f"Backend: {mode_label}; model: {self.model_name}")

        all_results: List[Dict[str, str]] = []
        if not self.use_server:
            self.load_model()

        with tqdm(total=len(audio_files), desc=f"Transcribing ({mode_label})") as pbar:
            for i in range(0, len(audio_files), self.batch_size):
                batch = audio_files[i : i + self.batch_size]
                for audio_file in batch:
                    all_results.append(self.transcribe_file(str(audio_file)))
                    pbar.update(1)
                self._save_jsonl(all_results, out_path)

        return str(out_path)

    def _save_jsonl(self, results: List[Dict], output_file: Path):
        with open(output_file, "w", encoding="utf-8") as f:
            for result in results:
                if "error" in result and not result["error"]:
                    del result["error"]
                json.dump(result, f, ensure_ascii=False)
                f.write("\n")

    def get_transcription_stats(self, jsonl_path: str) -> Dict:
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                data = [json.loads(line) for line in f]

            total = len(data)
            with_text = sum(1 for item in data if item.get("transcription"))
            errors = sum(1 for item in data if "error" in item)
            lengths = [len(item["transcription"]) for item in data if item.get("transcription")]

            mode_label = "server" if self.use_server else f"local ({self.device})"
            return {
                "total_files": total,
                "transcribed": with_text,
                "errors": errors,
                "success_rate": (with_text / total) if total > 0 else 0,
                "avg_transcription_length": (sum(lengths) / len(lengths)) if lengths else 0,
                "mode": mode_label,
                "model": self.model_name,
            }
        except Exception as e:
            return {"error": str(e)}


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Transcribe audio with fixed model OvozifyLabs/whisper-small-uz-v1"
    )
    parser.add_argument("--input", help="Input directory (default from config)")
    parser.add_argument("--output", help="Output JSONL file (auto if not set)")
    parser.add_argument("--config", default="config/config.yaml", help="Config file path")
    parser.add_argument("--mode", choices=["auto", "local", "server"], help="Runtime mode")
    parser.add_argument("--device", choices=["cuda", "cpu"], help="Device for local mode")
    parser.add_argument("--language", help="Language code (default: uz)")
    parser.add_argument("--batch-size", type=int, help="Batch size")
    parser.add_argument("--compute-type", choices=["float16", "float32"], help="Compute type")
    parser.add_argument("--server-url", help="Custom server URL for server mode")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    transcriber = WhisperTranscriber(args.config)
    transcriber.configure_runtime(
        mode=args.mode,
        device=args.device,
        batch_size=args.batch_size,
        language=args.language,
        compute_type=args.compute_type,
        server_url=args.server_url,
    )

    output_file = transcriber.transcribe_directory(args.input, args.output)
    if output_file:
        print(f"\nTranscriptions saved to: {output_file}")
        if args.stats or True:
            print("\nTranscription stats:")
            for k, v in transcriber.get_transcription_stats(output_file).items():
                if isinstance(v, float):
                    print(f"  {k}: {v:.2f}")
                else:
                    print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
