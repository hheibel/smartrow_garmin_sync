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
