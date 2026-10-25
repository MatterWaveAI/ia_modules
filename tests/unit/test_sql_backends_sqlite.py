"""
SQLCheckpointer and SQLConversationMemory against a real SQLite database,
through both of the objects they accept: a nexusql DatabaseManager and
ia_modules' NexuSQLAdapter.
"""
import asyncio

import pytest
from nexusql import DatabaseManager

from ia_modules.checkpoint.core import CheckpointSaveError
from ia_modules.checkpoint.sql import SQLCheckpointer
from ia_modules.database import MIGRATIONS_DIR, NexuSQLAdapter
from ia_modules.memory.core import MessageRole
from ia_modules.memory.sql import SQLConversationMemory


async def _open(kind):
    if kind == "manager":
        db = DatabaseManager("sqlite:///:memory:")
        assert await db.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)])
    else:
        db = NexuSQLAdapter("sqlite:///:memory:")
        assert await db.initialize(apply_schema=True)
    return db


@pytest.fixture(params=["manager", "adapter"])
async def db(request):
    db = await _open(request.param)
    yield db
    db.disconnect()


async def test_checkpoint_round_trip(db):
    cp = SQLCheckpointer(db)

    first = await cp.save_checkpoint("t1", "p1", "s1", 0, {"n": 1}, metadata={"by": "test"})
    await asyncio.sleep(0.002)  # distinct timestamps, so "latest" is well defined
    second = await cp.save_checkpoint(
        "t1", "p1", "s2", 1, {"n": 2}, step_name="Second", parent_checkpoint_id=first
    )

    latest = await cp.load_checkpoint("t1")
    assert latest.checkpoint_id == second
    assert latest.state == {"n": 2}
    assert latest.step_name == "Second"
    assert latest.parent_checkpoint_id == first

    by_id = await cp.load_checkpoint("t1", checkpoint_id=first)
    assert by_id.metadata == {"by": "test"}
    assert by_id.timestamp.year >= 2024

    listed = await cp.list_checkpoints("t1", pipeline_id="p1")
    assert [c.checkpoint_id for c in listed] == [second, first]
    assert await cp.list_checkpoints("other-thread") == []

    stats = await cp.get_checkpoint_stats(thread_id="t1")
    assert stats["total_checkpoints"] == 2
    assert stats["oldest_checkpoint"] <= stats["newest_checkpoint"]
    assert (await cp.get_checkpoint_stats())["threads"] == ["t1"]

    assert await cp.delete_checkpoint("t1", first) is True
    assert await cp.load_checkpoint("t1", checkpoint_id=first) is None
    assert await cp.delete_checkpoints("t1") == 1
    assert await cp.load_checkpoint("t1") is None


async def test_delete_checkpoints_before_and_keep_latest(db):
    cp = SQLCheckpointer(db)
    ids = []
    for index in range(3):
        ids.append(await cp.save_checkpoint("t1", "p1", f"s{index}", index, {"n": index}))
        await asyncio.sleep(0.002)
    oldest, middle, newest = ids

    assert await cp.delete_checkpoints("t1", keep_latest=2) == 1
    assert [c.checkpoint_id for c in await cp.list_checkpoints("t1")] == [newest, middle]

    cutoff = (await cp.load_checkpoint("t1", checkpoint_id=newest)).timestamp
    assert await cp.delete_checkpoints("t1", before=cutoff) == 1
    assert [c.checkpoint_id for c in await cp.list_checkpoints("t1")] == [newest]

    assert await cp.delete_checkpoints("t1", pipeline_id="other") == 0
    assert await cp.delete_checkpoints("t1") == 1
    assert await cp.list_checkpoints("t1") == []


async def test_checkpointer_requires_schema():
    db = DatabaseManager("sqlite:///:memory:")
    db.connect()
    try:
        with pytest.raises(CheckpointSaveError, match="pipeline_checkpoints table not found"):
            SQLCheckpointer(db)
    finally:
        db.disconnect()


async def test_conversation_memory_round_trip(db):
    memory = SQLConversationMemory(db)

    await memory.add_message("t1", "user", "hello there", user_id="u1", metadata={"lang": "en"})
    await asyncio.sleep(0.002)
    await memory.add_message("t1", "assistant", "hi, how can I help?", function_name="greet")

    messages = await memory.get_messages("t1")
    assert [m.content for m in messages] == ["hi, how can I help?", "hello there"]
    assert messages[1].role is MessageRole.USER
    assert messages[1].metadata == {"lang": "en"}
    assert messages[0].function_name == "greet"

    assert [m.user_id for m in await memory.get_user_messages("u1")] == ["u1"]
    assert [m.content for m in await memory.search_messages("help")] == ["hi, how can I help?"]

    stats = await memory.get_thread_stats("t1")
    assert stats["message_count"] == 2
    assert stats["first_message"] <= stats["last_message"]

    assert await memory.delete_thread("t1") == 2
    assert await memory.get_messages("t1") == []
