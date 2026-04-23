import unittest

from utils import access_secret_version


class TestSecretManager(unittest.TestCase):
    def test_access_test_password(self) -> None:
        """
        Verifies that the Google Cloud Secret Manager client can successfully
        authenticate and retrieve the 'test-password' secret.
        """
        try:
            payload = access_secret_version("test-credentials")

            # Assert that we actually retrieved a non-empty string
            self.assertTrue(
                payload is not None and len(payload) > 0,
                "The retrieved test password payload is empty.",
            )

        except Exception as e:
            self.fail(f"Failed to access the test-password secret. Error: {e}")


if __name__ == "__main__":
    unittest.main()
