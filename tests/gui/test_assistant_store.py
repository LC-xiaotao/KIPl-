"""The assistant's per-project conversation store."""

from types import SimpleNamespace

from kipi.gui.assistant.store import ConversationStore, project_key


def _snapshot(name, folder="/project", file=""):
    return SimpleNamespace(board_name=name, project_dir=folder, file=file)


def test_keys_are_stable_per_project():
    assert project_key(_snapshot("a")) == project_key(_snapshot("a"))
    assert project_key(_snapshot("a")) != project_key(_snapshot("b"))
    assert project_key(_snapshot("a", "/one")) != project_key(_snapshot("a", "/two"))
    assert project_key(_snapshot("a", file="/x/a.kipi.json.gz")) != \
        project_key(_snapshot("a", file="/x/b.kipi.json.gz"))
    assert project_key(None) == "no-board"


def test_store_roundtrip(tmp_path):
    store = ConversationStore(tmp_path)
    store.use("project")
    assert store.load() == {}

    store.save({"history": [{"role": "user", "content": "hi"}], "items": []})
    assert store.load()["history"][0]["content"] == "hi"

    store.clear()
    assert store.load() == {}


def test_a_corrupt_file_is_ignored(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    store = ConversationStore(tmp_path)
    store.use("broken")
    assert store.load() == {}
