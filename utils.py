import os
import tempfile
from absl import logging
from garminconnect import Garmin
from google.cloud import secretmanager
from google.cloud import storage
from config import PROJECT_ID, GCS_BUCKET_NAME

def access_secret_version(secret_id: str, version_id: str = "latest") -> str | None:
    """
    Accesses the payload for the given secret version using GCP Secret Manager.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    
    try:
        response = client.access_secret_version(request={"name": name})
        # Extract the payload as a string
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logging.error(f"Error retrieving secret {secret_id}: {e}")
        return None

def parse_credentials_payload(payload: str) -> tuple[str, str]:
    """
    Parses a multi-line string payload containing credentials.
    Expected format:
    username: <username>
    password: <password>
    
    Returns:
        A tuple of strings: (username, password)
        
    Raises:
        ValueError if the payload is missing a username or password.
    """
    username = None
    password = None
    
    for line in payload.splitlines():
        # Clean up leading/trailing whitespace on the whole line
        line = line.strip()
        
        # Look for username line (case-insensitive key)
        if line.lower().startswith("username:"):
            # Split only on the *first* colon in case the value itself has colons
            username = line.split(":", 1)[1].strip()
            
        # Look for password line (case-insensitive key)
        elif line.lower().startswith("password:"):
            password = line.split(":", 1)[1].strip()
            
    if username is None or password is None:
        raise ValueError("Payload must contain both 'username:' and 'password:' keys.")
        
    return username, password

def read_credentials(credential_secret_id: str) -> tuple[str, str]:
    """
    Retrieves and parses credentials from Google Cloud Secret Manager.
    
    Args:
        credential_secret_id: The ID of the secret containing the credentials.
        
    Returns:
        A tuple containing (username, password).
        
    Raises:
        ValueError if the payload is missing a username or password.
    """
    payload = access_secret_version(credential_secret_id)
    if not payload:
        raise RuntimeError(f"Could not securely access secret '{credential_secret_id}'. Ensure you are fully authenticated via 'gcloud auth application-default login'.")
    return parse_credentials_payload(payload)

def init_garmin_client() -> Garmin:
    """
    Initializes and logs into the Garmin client using cached tokens if possible.
    """
    username, password = read_credentials("garmin-credentials")
    
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    token_blob = bucket.blob("garmin_tokenstore/garmin_tokens.json")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Naming it .json ensures the library creates it as a file, not a directory
        tokenstore = os.path.join(tmp_dir, "garmin_tokens.json")
        
        # We only download if the blob exists on GCS and we either do not have a local file
        # or the local file is empty (e.g. due to a previous failed download)
        if token_blob.exists() and (not os.path.isfile(tokenstore) or os.path.getsize(tokenstore) == 0):
            logging.info("Tokenstore does not exist locally, downloading from GCS.")
            token_blob.download_to_filename(tokenstore)
            logging.info("Downloaded Garmin tokens from GCS.")
        
        try:
            # Try to initialize the client using saved session tokens FIRST
            client = Garmin(email=username, password=password)
            client.login(tokenstore)
            logging.info("Logged in to Garmin using cached tokens from GCS.")
        except Exception as e:
            logging.warning(f"Token login failed: {e}. Falling back to standard login.")
            # If tokens don't exist or expired, login manually
            client = Garmin(email=username, password=password)
            client.login()
            
            # Save the tokens immediately for the next time!
            logging.info("Logged in successfully, saving tokens to temp file %s and to GCS.", tokenstore)
            client.client.dump(tokenstore)
            
            token_blob.upload_from_filename(tokenstore)
            logging.info("Logged in and uploaded new tokens to GCS.")

    return client
