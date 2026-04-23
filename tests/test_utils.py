import unittest

from utils import parse_credentials_payload


class TestUtils(unittest.TestCase):
    def test_parse_valid_credentials(self) -> None:
        payload = "username: test_user\npassword: ::theweird_#2@.?#_p455w0rd!"
        username, password = parse_credentials_payload(payload)
        self.assertEqual(username, "test_user")

        # Important: this checks if the split algorithm drops colons in the password
        self.assertEqual(password, "::theweird_#2@.?#_p455w0rd!")

    def test_parse_with_extra_whitespace(self) -> None:
        payload = (
            "  username:    spaced_user   \n\n\n  password:   secure_pass123   "
        )
        username, password = parse_credentials_payload(payload)
        self.assertEqual(username, "spaced_user")
        self.assertEqual(password, "secure_pass123")

    def test_parse_with_mixed_case_keys(self) -> None:
        payload = "UserName: john_doe\nPassWORD: Password1"
        username, password = parse_credentials_payload(payload)
        self.assertEqual(username, "john_doe")
        self.assertEqual(password, "Password1")

    def test_parse_missing_password_raises_error(self) -> None:
        payload = "username: test_user"
        with self.assertRaisesRegex(
            ValueError,
            "Payload must contain both 'username:' and 'password:' keys.",
        ):
            parse_credentials_payload(payload)

    def test_parse_missing_username_raises_error(self) -> None:
        payload = "password: super_secret"
        with self.assertRaisesRegex(
            ValueError,
            "Payload must contain both 'username:' and 'password:' keys.",
        ):
            parse_credentials_payload(payload)

    def test_parse_empty_payload_raises_error(self) -> None:
        payload = ""
        with self.assertRaises(ValueError):
            parse_credentials_payload(payload)


if __name__ == "__main__":
    unittest.main()
