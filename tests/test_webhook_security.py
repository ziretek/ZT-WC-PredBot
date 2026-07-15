import re
import unittest

from wcbot.bot import webhook_credentials

FAKE_TOKEN = "123456:ABC-DEF_secret"
# Telegram secret_token charset: 1-256 chars of A-Z a-z 0-9 _ -
SECRET_CHARSET = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


class WebhookCredentialTests(unittest.TestCase):
    def test_url_path_hides_token_and_is_stable_across_restarts(self):
        path1, _ = webhook_credentials(FAKE_TOKEN)
        path2, _ = webhook_credentials(FAKE_TOKEN)

        self.assertEqual(path1, path2)
        self.assertNotIn(FAKE_TOKEN, path1)
        self.assertNotIn("123456", path1)
        self.assertTrue(SECRET_CHARSET.match(path1))

    def test_configured_secret_is_used_verbatim(self):
        _, secret = webhook_credentials(FAKE_TOKEN, configured_secret="my-secret_123")
        self.assertEqual(secret, "my-secret_123")

    def test_generated_secret_is_random_and_not_token_derived(self):
        path, secret1 = webhook_credentials(FAKE_TOKEN)
        _, secret2 = webhook_credentials(FAKE_TOKEN)

        self.assertNotEqual(secret1, secret2)
        self.assertNotEqual(secret1, path)
        self.assertTrue(SECRET_CHARSET.match(secret1))


if __name__ == "__main__":
    unittest.main()
