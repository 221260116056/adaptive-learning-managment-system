import hashlib
import time
import logging

logger = logging.getLogger(__name__)

def generate_secure_token(user_id, module_id, secret, expiry_seconds=7200):
    """
    Generates a secure, time-bound token for video streaming.
    Format: <sha256_hash>.<expiry_timestamp>
    """
    expiry_timestamp = int(time.time()) + expiry_seconds
    token_str = f"{user_id}:{module_id}:{expiry_timestamp}:{secret}"
    token_hash = hashlib.sha256(token_str.encode('utf-8')).hexdigest()
    
    return f"{token_hash}.{expiry_timestamp}"


def verify_secure_token(token_payload, user_id, module_id, secret):
    """
    Verifies the secure streaming token.
    Checks both cryptographic integrity and time expiration.
    Returns (is_valid: bool, error_message: str)
    """
    if not token_payload or '.' not in token_payload:
        logger.warning(f"VideoAccess: Missing or invalid token format for user {user_id}, module {module_id}")
        return False, "Invalid token format."

    token_hash, expiry_str = token_payload.split('.', 1)
    
    try:
        expiry_timestamp = int(expiry_str)
    except ValueError:
        logger.warning(f"VideoAccess: Malformed expiry for user {user_id}, module {module_id}")
        return False, "Malformed expiry timestamp."

    # Check expiration
    if int(time.time()) > expiry_timestamp:
        logger.warning(f"VideoAccess: Token expired for user {user_id}, module {module_id}")
        return False, "Streaming token has expired."

    # Verify signature
    expected_str = f"{user_id}:{module_id}:{expiry_timestamp}:{secret}"
    expected_hash = hashlib.sha256(expected_str.encode('utf-8')).hexdigest()

    if token_hash != expected_hash:
        logger.warning(f"VideoAccess: Hash mismatch for user {user_id}, module {module_id}")
        return False, "Invalid token signature."

    # Valid token
    logger.info(f"VideoAccess: Successful access for user {user_id}, module {module_id}")
    return True, ""
