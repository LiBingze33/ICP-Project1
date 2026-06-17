import unittest

from security.post_call_audit import sanitize_for_audit


class PostCallAuditTests(unittest.TestCase):
    def test_sanitizes_sensitive_audit_fields(self):
        sanitized = sanitize_for_audit(
            {
                "tool_name": "demo_fake_secret_api",
                "tool_args": {
                    "workspace_path": "C:\\Users\\tuetm\\secret-workspace",
                    "token": "secret-token-value",
                    "message": "hello",
                },
            }
        )

        self.assertEqual("[redacted]", sanitized["tool_args"]["workspace_path"])
        self.assertEqual("[redacted]", sanitized["tool_args"]["token"])
        self.assertEqual("hello", sanitized["tool_args"]["message"])

    def test_truncates_long_audit_strings(self):
        sanitized = sanitize_for_audit({"preview": "a" * 250})

        self.assertTrue(sanitized["preview"].endswith("...[truncated]"))
        self.assertLess(len(sanitized["preview"]), 230)


if __name__ == "__main__":
    unittest.main()
