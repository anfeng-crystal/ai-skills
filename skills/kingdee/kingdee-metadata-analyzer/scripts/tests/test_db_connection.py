import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from db_connection import (  # noqa: E402
    MetadataDbConnectionError,
    connect_with_retry,
    is_retryable_connection_error,
)


class FakeDbError(Exception):
    def __init__(self, message, pgcode=None):
        super().__init__(message)
        self.pgcode = pgcode


class DbConnectionTest(unittest.TestCase):
    @patch("db_connection.time.sleep")
    def test_transient_disconnect_is_retried_until_success(self, sleep):
        attempts = []
        warnings = []
        connection = object()

        def connect(**kwargs):
            attempts.append(kwargs)
            if len(attempts) < 3:
                raise FakeDbError("server closed the connection unexpectedly")
            return connection

        result = connect_with_retry(connect, {"host": "dev-db"}, warn=warnings.append)

        self.assertIs(result, connection)
        self.assertEqual(3, len(attempts))
        self.assertEqual([0.25, 0.5], [call.args[0] for call in sleep.call_args_list])
        self.assertEqual(2, len(warnings))

    @patch("db_connection.time.sleep")
    def test_authentication_failure_is_not_retried_or_exposed(self, sleep):
        calls = 0

        def connect(**_kwargs):
            nonlocal calls
            calls += 1
            raise FakeDbError("password authentication failed for host secret-db", "28P01")

        with self.assertRaises(MetadataDbConnectionError) as raised:
            connect_with_retry(connect, {"password": "secret"})

        self.assertEqual(1, calls)
        sleep.assert_not_called()
        self.assertNotIn("secret-db", str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))

    @patch("db_connection.time.sleep")
    def test_transient_failure_stops_after_bounded_attempts(self, sleep):
        calls = 0

        def connect(**_kwargs):
            nonlocal calls
            calls += 1
            raise FakeDbError("connection reset by peer", "08006")

        with self.assertRaisesRegex(MetadataDbConnectionError, "已尝试 3 次"):
            connect_with_retry(connect, {})

        self.assertEqual(3, calls)
        self.assertEqual(2, sleep.call_count)

    def test_retryable_sqlstate_and_message_detection(self):
        self.assertTrue(is_retryable_connection_error(FakeDbError("opaque", "08001")))
        self.assertTrue(is_retryable_connection_error(FakeDbError("timeout expired")))
        self.assertFalse(is_retryable_connection_error(FakeDbError("bad password", "28P01")))


if __name__ == "__main__":
    unittest.main()
