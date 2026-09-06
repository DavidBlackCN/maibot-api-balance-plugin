import asyncio
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sdk = types.ModuleType("maibot_sdk")
sdk.Command = lambda *_args, **_kwargs: lambda func: func
sdk.MaiBotPlugin = type("MaiBotPlugin", (), {"__init__": lambda self: None})
sdk.PluginConfigBase = type("PluginConfigBase", (), {})
sdk.Field = lambda default=None, default_factory=None, **_kwargs: default_factory() if default_factory else default
sys.modules.setdefault("maibot_sdk", sdk)

import plugin as plugin_module
from libs.providers import _BalanceRecord


def ns(**kwargs):
    return SimpleNamespace(**kwargs)


def make_plugin(instances, *, groups=None, output_format="text"):
    obj = plugin_module.APIBalancePlugin()
    obj.config = ns(
        settings=ns(timeout=10, output_format=output_format, admin_only=False, admin_user_ids=[]),
        broadcast=ns(enabled=True, group_ids=groups or [], time="09:00", header="每日余额"),
        api_instances=instances,
    )
    obj.ctx = ns()
    return obj


def instance(ptype, **kwargs):
    values = dict(
        type=ptype, enabled=True, label="", api_key="key", base_url="", user_id="",
        access_key_id="", secret_access_key="",
    )
    values.update(kwargs)
    return ns(**values)


class PluginTests(unittest.TestCase):
    def test_siliconflow_is_kept_but_never_collected(self):
        obj = make_plugin([instance("siliconflow"), instance("deepseek")])
        self.assertEqual([p.display_name for p in obj._collect_providers()], ["DeepSeek"])

    def test_volcengine_requires_both_credentials(self):
        obj = make_plugin([
            instance("volcengine", api_key="", access_key_id="AK", secret_access_key=""),
            instance("volcengine", api_key="", access_key_id="AK", secret_access_key="SK"),
        ])
        providers = obj._collect_providers()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].access_key_id, "AK")

    def test_time_validation_and_group_normalization(self):
        obj = make_plugin([], groups=[" 123 ", "123", "", "456"])
        self.assertEqual(obj._parse_broadcast_time("09:05"), (9, 5))
        self.assertIsNone(obj._parse_broadcast_time("9:05"))
        self.assertIsNone(obj._parse_broadcast_time("24:00"))
        self.assertEqual(obj._broadcast_groups(), ["123", "456"])

    def test_off_schedule_does_not_backfill(self):
        obj = make_plugin([], groups=["123"])
        now = datetime(2026, 9, 6, 9, 1, tzinfo=timezone(timedelta(hours=8)))
        self.assertFalse(asyncio.run(obj._run_scheduled_broadcast(now)))

    def test_scheduled_broadcast_queries_once_and_deduplicates(self):
        async def scenario(state_path):
            old_path = plugin_module._BROADCAST_STATE_PATH
            plugin_module._BROADCAST_STATE_PATH = state_path
            obj = make_plugin([instance("deepseek")], groups=["1", "2"])
            calls = {"query": 0, "groups": []}

            async def query(providers):
                calls["query"] += 1
                return [(providers[0], _BalanceRecord("DeepSeek", status="正常", status_ok=True))]

            async def send(group, nodes):
                calls["groups"].append((group, nodes))

            async def render(_records, _now):
                return None

            obj._query_records = query
            obj._send_broadcast_to_group = send
            obj._render_records_image = render
            now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone(timedelta(hours=8)))
            try:
                self.assertTrue(await obj._run_scheduled_broadcast(now))
                self.assertFalse(await obj._run_scheduled_broadcast(now))
            finally:
                plugin_module._BROADCAST_STATE_PATH = old_path
            self.assertEqual(calls["query"], 1)
            self.assertEqual([item[0] for item in calls["groups"]], ["1", "2"])
            self.assertTrue(calls["groups"][0][1][0]["segments"][0]["content"].startswith("每日余额"))

        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(scenario(plugin_module.Path(directory) / "state.json"))

    def test_broadcast_nodes_follow_output_format(self):
        async def scenario(output_format, image, expected_types, state_path):
            old_path = plugin_module._BROADCAST_STATE_PATH
            plugin_module._BROADCAST_STATE_PATH = state_path
            obj = make_plugin([instance("deepseek")], groups=["1"], output_format=output_format)
            captured = []

            async def query(providers):
                return [(providers[0], _BalanceRecord("DeepSeek", status="正常", status_ok=True))]

            async def render(_records, _now):
                return image

            async def send(_group, nodes):
                captured.extend(nodes)

            obj._query_records = query
            obj._render_records_image = render
            obj._send_broadcast_to_group = send
            now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone(timedelta(hours=8)))
            try:
                await obj._run_scheduled_broadcast(now)
            finally:
                plugin_module._BROADCAST_STATE_PATH = old_path
            self.assertEqual([node["segments"][0]["type"] for node in captured], expected_types)

        cases = [
            ("text", None, ["text", "text"]),
            ("image", "base64-image", ["text", "image"]),
            ("both", "base64-image", ["text", "image", "text"]),
            ("image", None, ["text", "text"]),
        ]
        for index, (fmt, image, expected) in enumerate(cases):
            with self.subTest(output_format=fmt, image=bool(image)), tempfile.TemporaryDirectory() as directory:
                asyncio.run(scenario(fmt, image, expected, plugin_module.Path(directory) / f"state-{index}.json"))
