"""The model-fetch job: only locked models, exactly the locked bytes, and no network when they are already there."""

import json

import pytest

from voice import fetch_job, modelstore
from voice.modelstore import ModelSpec, fetch, write_lock


class FakeHub:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.downloads: list[str] = []

    def resolve_revision(self, repo: str) -> str:
        raise AssertionError("the job must never ask for the newest revision")

    def list_files(self, repo: str, revision: str) -> list[str]:
        assert revision == "rev-1"
        return list(self.files)

    def download(self, repo, filename, revision, staging):
        self.downloads.append(filename)
        target = staging / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.files[filename])
        return target


FILES = {"config.json": b"{}", "model.bin": b"weights", "tokenizer.json": b"tok", "vocabulary.txt": b"v"}


class FirstFetch(FakeHub):
    def resolve_revision(self, repo: str) -> str:
        return "rev-1"


@pytest.fixture
def job(monkeypatch, tmp_path):
    """A catalog with one model, its lock file written by a first fetch elsewhere, and an empty models directory."""
    monkeypatch.setattr(
        modelstore,
        "CATALOG",
        {"stt-test": ModelSpec(repo="org/whisper", patterns=modelstore.WHISPER_FILES, licence="t")},
    )
    monkeypatch.setattr(fetch_job, "CATALOG", modelstore.CATALOG)
    lock: dict = {}
    fetch("stt-test", tmp_path / "workstation", lock, FirstFetch(FILES))
    lock_path = tmp_path / "models.lock.json"
    write_lock(lock_path, lock)
    return tmp_path / "models", lock_path


def run(job, hub, names=("stt-test",)):
    models_dir, lock_path = job
    return fetch_job.run(list(names), models_dir, lock_path, lambda: hub)


def test_empty_volume_downloads_the_locked_revision(job, capsys):
    hub = FakeHub(FILES)
    assert run(job, hub) == 0
    assert sorted(hub.downloads) == sorted(FILES)
    assert sorted(p.name for p in (job[0] / "stt-test").iterdir()) == sorted(FILES)
    out = capsys.readouterr().out
    assert "OK   stt-test: org/whisper @ rev-1, 4 files, 0 MB, downloaded and verified" in out
    assert out.strip().endswith("1/1 models match models.lock.json")


def test_warm_volume_needs_no_hub_at_all(job, capsys):
    run(job, FakeHub(FILES))

    def no_hub():
        raise AssertionError("no hub client may be created when the files already match")

    assert fetch_job.run(["stt-test"], job[0], job[1], no_hub) == 0
    assert "already in" in capsys.readouterr().out.splitlines()[-2]


def test_a_file_that_differs_from_the_lock_fails_the_job(job, capsys):
    hub = FakeHub({**FILES, "model.bin": b"other weights"})
    assert run(job, hub) == 1
    out = capsys.readouterr().out
    assert "FAIL stt-test: files of org/whisper@rev-1 differ from models.lock.json" in out
    assert "model.bin differs from the lock" in out
    assert "0/1 models match" in out


def test_a_changed_file_on_the_volume_is_replaced(job):
    run(job, FakeHub(FILES))
    (job[0] / "stt-test" / "model.bin").write_bytes(b"WEIGHTS")  # same size, other bytes
    hub = FakeHub(FILES)
    assert run(job, hub) == 0
    assert hub.downloads == ["model.bin"]
    assert (job[0] / "stt-test" / "model.bin").read_bytes() == b"weights"


def test_a_file_the_lock_does_not_list_is_removed(job, capsys):
    run(job, FakeHub(FILES))
    (job[0] / "stt-test" / "old-vocabulary.json").write_bytes(b"left over")
    assert fetch_job.run(["stt-test"], job[0], job[1], lambda: None) == 0
    assert not (job[0] / "stt-test" / "old-vocabulary.json").exists()
    assert "removed old-vocabulary.json: not in the lock" in capsys.readouterr().out


def test_a_model_that_is_not_locked_is_refused_and_the_lock_is_never_written(job, capsys):
    models_dir, lock_path = job
    lock_path.write_text("{}\n", encoding="utf-8")
    assert run(job, FakeHub(FILES)) == 1
    assert "FAIL stt-test: not in models.lock.json" in capsys.readouterr().out
    assert json.loads(lock_path.read_text(encoding="utf-8")) == {}
    assert not (models_dir / "stt-test").exists()


def test_one_failure_fails_the_job_but_every_model_is_reported(job, capsys):
    assert run(job, FakeHub(FILES), names=("stt-test", "stt-unknown")) == 1
    out = capsys.readouterr().out
    assert "OK   stt-test" in out
    assert "FAIL stt-unknown: not in the catalog" in out
    assert "1/2 models match" in out


def test_a_download_error_is_one_line(job, capsys):
    class Down(FakeHub):
        def list_files(self, repo, revision):
            raise ConnectionError("no route to the model host")

    assert run(job, Down(FILES)) == 1
    assert "FAIL stt-test: download failed (ConnectionError: no route to the model host)" in capsys.readouterr().out


def test_no_names_and_no_lock_file_fail(job, tmp_path, capsys):
    assert fetch_job.run([], job[0], job[1], lambda: None) == 1
    assert fetch_job.run(["stt-test"], job[0], tmp_path / "missing.json", lambda: None) == 1
    out = capsys.readouterr().out
    assert "no model named" in out
    assert "missing.json does not exist" in out


def test_check_passes_on_exactly_the_locked_files_and_needs_no_hub(job, capsys):
    run(job, FakeHub(FILES))
    capsys.readouterr()
    assert fetch_job.check(["stt-test"], job[0], job[1]) == 0
    out = capsys.readouterr().out
    assert "OK   stt-test: 4 files match the lock" in out
    assert out.strip().endswith("1/1 models match models.lock.json")


def test_check_reports_and_changes_nothing(job, capsys):
    run(job, FakeHub(FILES))
    directory = job[0] / "stt-test"
    (directory / "model.bin").write_bytes(b"WEIGHTS")
    (directory / "extra.txt").write_bytes(b"x")
    assert fetch_job.check(["stt-test"], job[0], job[1]) == 1
    out = capsys.readouterr().out
    assert "model.bin differs from the lock" in out
    assert "extra.txt is not in the lock" in out
    assert (directory / "model.bin").read_bytes() == b"WEIGHTS"  # nothing replaced
    assert (directory / "extra.txt").exists()  # nothing removed


def test_check_on_an_empty_volume_fails(job, capsys):
    assert fetch_job.check(["stt-test"], job[0], job[1]) == 1
    assert "does not exist" in capsys.readouterr().out
    assert not job[0].exists()  # not even the models directory is created


def test_main_check_flag_never_creates_a_hub_client(job, monkeypatch, capsys):
    run(job, FakeHub(FILES))
    monkeypatch.setenv("MODELS_DIR", str(job[0]))
    monkeypatch.setenv("MODELS_LOCK", str(job[1]))

    class NoHub:
        def __init__(self):
            raise AssertionError("--check must not create a hub client")

    monkeypatch.setattr(fetch_job, "HuggingFaceHub", NoHub)
    assert fetch_job.main(["--check", "stt-test"]) == 0
    assert fetch_job.main(["--check"]) == 1
