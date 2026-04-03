import json
from pathlib import Path
import tempfile


def test_export_outputs_by_video_creates_flat_layout():
    # Import is intentionally inside the test to keep collection fast.
    from main import AudioPipeline

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        outputs_dir = base / "outputs"
        vad_dir = base / "vad_segments"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        vad_dir.mkdir(parents=True, exist_ok=True)

        # Simulate multi-level segment names that should collapse into one video folder.
        rows = [
            {
                "file_name": "Bloger_1_UCbjTJ0b0TA_seg0000_seg0000.wav",
                "transcription": "a",
            },
            {
                "file_name": "Bloger_1_UCbjTJ0b0TA_seg0000_seg0001.wav",
                "transcription": "b",
            },
            {
                "file_name": "Bloger_1_UCbjTJ0b0TA_seg0001_seg0000.wav",
                "transcription": "c",
            },
        ]

        for r in rows:
            (vad_dir / r["file_name"]).write_bytes(b"")

        transcription_file = base / "transcriptions_filtered.jsonl"
        with open(transcription_file, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # Create a pipeline instance without running __init__ (avoids heavy deps).
        p = AudioPipeline.__new__(AudioPipeline)
        p.outputs_dir = outputs_dir
        p.job_id = 123

        AudioPipeline._export_outputs_by_video(p, str(transcription_file), vad_segments_dir=str(vad_dir))

        job_root = outputs_dir / "jobs" / "job_123"
        assert job_root.exists()
        video_dirs = [d for d in job_root.iterdir() if d.is_dir()]
        assert len(video_dirs) == 1

        video_dir = video_dirs[0]
        # Only WAV segments + transcription.json
        files = sorted([p.name for p in video_dir.iterdir() if p.is_file()])
        assert "transcription.json" in files
        assert all(name.endswith(".wav") or name == "transcription.json" for name in files)
        assert "vad_segments" not in [p.name for p in video_dir.iterdir()]
        assert "metadata" not in [p.name for p in video_dir.iterdir()]

        expected_wavs = {"seg0000_0000.wav", "seg0000_0001.wav", "seg0001_0000.wav"}
        assert expected_wavs.issubset(set(files))

        data = json.loads((video_dir / "transcription.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)
        got = {(x["file_name"], x["transcription"]) for x in data}
        assert got == {
            ("seg0000_0000.wav", "a"),
            ("seg0000_0001.wav", "b"),
            ("seg0001_0000.wav", "c"),
        }
