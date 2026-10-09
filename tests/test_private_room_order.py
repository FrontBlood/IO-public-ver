import asyncio
import unittest
from unittest.mock import AsyncMock

from services import private_room_manager


class FakeChannel:
    def __init__(self, channel_id, guild, position=0):
        self.id = channel_id
        self.guild = guild
        self.position = position
        self.move = AsyncMock()
        self.edit = AsyncMock()


class FakeCategory:
    def __init__(self, channels):
        self.voice_channels = channels


class PrivateRoomOrderTests(unittest.TestCase):
    def tearDown(self):
        private_room_manager._guild_move_locks.clear()

    def test_move_appends_to_target_instead_of_reusing_source_position(self):
        guild = type("Guild", (), {"id": 1, "voice_channels": []})()
        moving = FakeChannel(20, guild, position=999)
        category = FakeCategory([FakeChannel(10, guild), FakeChannel(30, guild)])

        asyncio.run(
            private_room_manager.move_channel_to_category_position(
                moving, category, reason="test"
            )
        )

        moving.move.assert_awaited_once_with(category=category, end=True, reason="test")
        moving.edit.assert_not_awaited()

    def test_empty_target_also_uses_append_semantics(self):
        guild = type("Guild", (), {"id": 1, "voice_channels": []})()
        moving = FakeChannel(20, guild)
        category = FakeCategory([])

        asyncio.run(
            private_room_manager.move_channel_to_category_position(
                moving, category, reason="test"
            )
        )

        moving.move.assert_awaited_once_with(category=category, end=True, reason="test")


class ActiveOrderRestoreTests(unittest.TestCase):
    def test_snapshot_uses_current_admin_order(self):
        guild = type("Guild", (), {"id": 1})()
        category = FakeCategory(
            [
                FakeChannel(30, guild, position=2),
                FakeChannel(10, guild, position=0),
                FakeChannel(20, guild, position=1),
            ]
        )

        self.assertEqual(
            private_room_manager._snapshot_category_order(category),
            [10, 20, 30],
        )

    def test_restore_reapplies_snapshot_after_archiving(self):
        http = type("HTTP", (), {})()
        http.bulk_channel_update = AsyncMock()
        state = type("State", (), {"http": http})()
        guild = type("Guild", (), {"id": 1, "_state": state})()
        first = FakeChannel(10, guild, position=0)
        archived = FakeChannel(20, guild, position=1)
        last = FakeChannel(30, guild, position=2)
        category = FakeCategory([last, archived, first])

        restored = asyncio.run(
            private_room_manager._restore_active_category_order(
                guild,
                category,
                [10, 20, 30],
                {20},
            )
        )

        self.assertTrue(restored)
        http.bulk_channel_update.assert_awaited_once_with(
            1,
            [
                {"id": 10, "position": 0},
                {"id": 30, "position": 1},
            ],
            reason="private_room_active_order_restore",
        )

    def test_restore_keeps_new_channels_at_the_end(self):
        http = type("HTTP", (), {})()
        http.bulk_channel_update = AsyncMock()
        state = type("State", (), {"http": http})()
        guild = type("Guild", (), {"id": 1, "_state": state})()
        first = FakeChannel(10, guild, position=2)
        second = FakeChannel(20, guild, position=0)
        newly_active = FakeChannel(99, guild, position=1)
        category = FakeCategory([second, newly_active, first])

        restored = asyncio.run(
            private_room_manager._restore_active_category_order(
                guild,
                category,
                [10, 20],
                set(),
            )
        )

        self.assertTrue(restored)
        payload = http.bulk_channel_update.await_args.args[1]
        self.assertEqual([item["id"] for item in payload], [10, 20, 99])
