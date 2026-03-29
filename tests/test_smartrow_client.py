import unittest
import sys
from unittest.mock import patch, MagicMock
import requests

# Mock google.cloud modules so that tests can run without having them installed
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.secretmanager'] = MagicMock()

from smartrow_client import SmartRowClient

class TestSmartRowClient(unittest.TestCase):
    """
    Test suite for SmartRowClient class focusing on mocking external dependencies
    and HTTP requests via the requests library.
    """

    @patch('smartrow_client.read_credentials')
    def test_init(self, mock_read_credentials):
        """
        Test the initialization of SmartRowClient.
        
        Verifies that:
        - The client reads credentials successfully upon instantiation.
        - The credentials, base_url, and an empty session state are properly assigned.
        - read_credentials is only called once with the correct secret ID.
        """
        mock_read_credentials.return_value = ("testuser", "testpass")
        client = SmartRowClient()
        self.assertEqual(client.username, "testuser")
        self.assertEqual(client.password, "testpass")
        self.assertIsNone(client.session)
        self.assertEqual(client.base_url, "https://smartrow.fit")
        mock_read_credentials.assert_called_once_with("smartrow-credentials")

    @patch('smartrow_client.read_credentials')
    @patch('smartrow_client.requests.Session')
    def test_login_success(self, mock_session_class, mock_read_credentials):
        """
        Test successful login behavior.
        
        Verifies that:
        - The _login method instantiates a new requests.Session.
        - A GET request is submitted to the correct login endpoint.
        - Standard Basic Authentication headers using the stored credentials are included.
        - The generated session is cached successfully.
        """
        mock_read_credentials.return_value = ("testuser", "testpass")
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock the get response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        client = SmartRowClient()
        client._login()

        self.assertIsNotNone(client.session)
        self.assertEqual(client.session, mock_session)
        mock_session.get.assert_called_once()
        args, kwargs = mock_session.get.call_args
        self.assertEqual(args[0], "https://smartrow.fit/api/account/0")
        self.assertIn("Authorization", kwargs["headers"])

    @patch('smartrow_client.read_credentials')
    @patch('smartrow_client.requests.Session')
    def test_login_failure(self, mock_session_class, mock_read_credentials):
        """
        Test failure handling during login.
        
        Verifies that:
        - If the API returns a failing status code (e.g. 401 Unauthorized), the login process raises an HTTPError.
        - The session behaves correctly under an exception context and the client bubbles up the error appropriately.
        """
        mock_read_credentials.return_value = ("testuser", "testpass")
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock the get response to raise an exception
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Login Failed")
        mock_session.get.return_value = mock_response

        client = SmartRowClient()
        with self.assertRaises(requests.exceptions.HTTPError):
            client._login()
            
    @patch('smartrow_client.read_credentials')
    def test_get_activities(self, mock_read_credentials):
        """
        Test retrieving the summary feed of public game activities.
        
        Verifies that:
        - A mock session correctly mocks the retrieval of JSON activity lists.
        - The method parses the JSON response and returns it to the caller.
        - Target URL precisely matches the intended /api/public-game endpoint.
        """
        mock_read_credentials.return_value = ("testuser", "testpass")
        client = SmartRowClient()
        
        # Mock session and its get method
        client.session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "name": "activity 1"}]
        client.session.get.return_value = mock_response
        
        activities = client.get_activities()
        
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["id"], 1)
        client.session.get.assert_called_once_with("https://smartrow.fit/api/public-game")

    @patch('smartrow_client.read_credentials')
    def test_get_activity_tcx(self, mock_read_credentials):
        """
        Test retrieving a single activity payload exported as TCX format.
        
        Verifies that:
        - A dedicated GET request using the specific activity ID is launched.
        - The text representation of the response payload is successfully extracted and returned.
        - The exact endpoint /api/export/tcx/{activity_id} is hit.
        """
        mock_read_credentials.return_value = ("testuser", "testpass")
        client = SmartRowClient()
        
        # Mock session and its get method
        client.session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<tcx>test data</tcx>"
        client.session.get.return_value = mock_response
        
        tcx_data = client.get_activity_tcx(123)
        
        self.assertEqual(tcx_data, "<tcx>test data</tcx>")
        client.session.get.assert_called_once_with("https://smartrow.fit/api/export/tcx/123")

if __name__ == '__main__':
    unittest.main()
