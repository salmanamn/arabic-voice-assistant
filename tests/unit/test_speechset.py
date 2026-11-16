"""Test-set plumbing: manifests, picking your newest recordings, selecting and extracting FLEURS sentences."""

import io
import os
import tarfile

import pytest

from voice.speechset import (
    Utterance,
    extract_members,
    newest_recordings,
    read_manifest,
    select_fleurs,
    write_manifest,
)


def test_manifest_round_trip_sorted_by_id(tmp_path):
    utterances = [
        Utterance("S02", "S02.m4a", "كم الساعة؟", 2.1, "b" * 64, "gulf"),
        Utterance("S01", "S01.m4a", "ما هي عاصمة البحرين؟", 3.0, "a" * 64),
    ]
    write_manifest(tmp_path / "own", utterances)
    assert [u.id for u in read_manifest(tmp_path / "own")] == ["S01", "S02"]
    assert read_manifest(tmp_path / "own")[1].style == "gulf"
    assert "عاصمة" in (tmp_path / "own" / "manifest.jsonl").read_text(encoding="utf-8")  # readable Arabic


def test_missing_manifest_says_what_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"speech_set\.py"):
        read_manifest(tmp_path)


def test_newest_recordings_in_recording_order(tmp_path):
    for i, name in enumerate(["old.m4a", "Recording.m4a", "Recording (2).m4a", "Recording (3).m4a", "notes.txt"]):
        path = tmp_path / name
        path.write_bytes(b"x")
        os.utime(path, (1_000 + i, 1_000 + i))
    assert [p.name for p in newest_recordings(tmp_path, 3)] == [
        "Recording.m4a",
        "Recording (2).m4a",
        "Recording (3).m4a",
    ]


def test_newest_recordings_needs_enough_files(tmp_path):
    (tmp_path / "a.m4a").write_bytes(b"x")
    with pytest.raises(ValueError, match="1 audio files, 2 needed"):
        newest_recordings(tmp_path, 2)


TSV = "\n".join(
    [
        "1907\t111.wav\tالجملة الأولى.\tالجملة الأولى\t13\t96000\tFEMALE",  # 6 s
        "1907\t112.wav\tالجملة الأولى.\tالجملة الأولى\t13\t99000\tMALE",  # same sentence, second speaker
        "15\t210.wav\tجملة طويلة جدا.\tجملة طويلة جدا\t14\t480000\tMALE",  # 30 s: too long
        "300\t300.wav\tجملة ثالثة.\tجملة ثالثة\t10\t64000\tMALE",
        "bad line",
    ]
)


def test_select_fleurs_one_recording_per_sentence_lowest_id_first_and_short_only():
    rows = select_fleurs(TSV, count=5, max_seconds=20)
    assert [(r["sentence"], r["file_name"]) for r in rows] == [(300, "300.wav"), (1907, "111.wav")]
    assert rows[1]["text"] == "الجملة الأولى."  # raw transcription, punctuation kept (normalised at scoring)
    assert rows[1]["seconds"] == 6.0
    assert len(select_fleurs(TSV, count=1, max_seconds=20)) == 1


def make_tar(path, members: dict[str, bytes], symlink: str | None = None):
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if symlink:
            info = tarfile.TarInfo(symlink)
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)


def test_extract_members_writes_only_selected_files_under_our_names(tmp_path):
    archive = tmp_path / "test.tar.gz"
    make_tar(
        archive, {"test/111.wav": b"one", "test/300.wav": b"three", "../../evil.wav": b"no"}, symlink="test/link.wav"
    )
    out = tmp_path / "out"
    missing = extract_members(
        archive, {"111.wav": out / "F0001.wav", "link.wav": out / "F0002.wav", "999.wav": out / "x.wav"}
    )
    assert (out / "F0001.wav").read_bytes() == b"one"
    assert missing == {"link.wav", "999.wav"}  # a symlink is not a regular file
    assert sorted(p.name for p in out.iterdir()) == ["F0001.wav"]
    assert not (tmp_path.parent / "evil.wav").exists()
