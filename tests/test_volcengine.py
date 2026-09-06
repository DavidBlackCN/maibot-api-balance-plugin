from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from libs.providers import _BalanceBusinessError, _VolcEngineProvider


def make_provider():
    return _VolcEngineProvider("AKIDEXAMPLE", "SECRET", "", 10)


class VolcEngineTests(unittest.TestCase):
    def test_signature_is_stable(self):
        request = make_provider()._build_signed_request(
            datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        )
        self.assertEqual(request.full_url, "https://open.volcengineapi.com/?Action=QueryBalanceAcct&Version=2022-01-01")
        self.assertEqual(request.get_header("X-date"), "20240102T030405Z")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertIn("/cn-north-1/billing/request", request.get_header("Authorization"))
        self.assertTrue(request.get_header("Authorization").endswith(
            "Signature=a5d602ace2e99e8183addb1a6bcf8a228c25e41fa1db0f2c90945c68fca7d747"
        ))

    def test_record_preserves_zero_and_negative_values(self):
        record = make_provider().to_record({"Result": {
            "AvailableBalance": "-1.25", "CashBalance": "0",
            "CreditLimit": "50", "ArrearsBalance": "1.25", "FreezeAmount": "0",
        }})
        self.assertFalse(record.status_ok)
        self.assertEqual(record.entries[0]["total"], "-1.25")
        self.assertEqual(record.entries[0]["granted"], "0.00")
        self.assertIn("欠费 ￥1.25", record.note)

    def test_missing_balance_is_not_rendered_as_zero(self):
        record = make_provider().to_record({"Result": {"AccountID": 123}})
        self.assertFalse(record.status_ok)
        self.assertEqual(record.entries, [])
        self.assertIn("未包含余额字段", record.note)

    def test_business_error_is_reported(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def read(self):
                return b'{"ResponseMetadata":{"Error":{"Code":"SignatureDoesNotMatch","Message":"bad signature"}}}'

        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaisesRegex(_BalanceBusinessError, "SignatureDoesNotMatch"):
                make_provider().fetch_sync()
