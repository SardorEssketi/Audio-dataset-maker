def test_default_config_has_download_section():
    # Import inside test: backend/__init__.py imports app at module import.
    from backend.services.config_service import load_default_config

    cfg = load_default_config()
    assert isinstance(cfg, dict)
    assert "download" in cfg, "Default config must include 'download' section"
    assert "paths" in cfg, "Default config must include 'paths' section"


def test_expand_dotted_overrides_builds_nested_dicts():
    from backend.services.config_service import expand_dotted_overrides

    expanded = expand_dotted_overrides(
        {
            "download.max_workers": 4,
            "download.scrape.enabled": True,
            "huggingface.repo_id": "a/b",
        }
    )

    assert expanded["download"]["max_workers"] == 4
    assert expanded["download"]["scrape"]["enabled"] is True
    assert expanded["huggingface"]["repo_id"] == "a/b"

