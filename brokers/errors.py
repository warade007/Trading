MESSAGES = {
    "CATALOG_REQUIRED": "Sync the NSE instrument list first.",
    "INSTRUMENT_NOT_FOUND": "The selected NSE instrument was not found in this saved master. Sync instruments and select it again.",
    "DOWNLOAD_BUSY": "A historical request is running. Wait before retrying; interrupted requests may be resumed after ten minutes.",
    "INVALID_MARKET_DATA": "Broker data or its local archive failed validation. No unvalidated candles were accepted.",
    "DATA_REJECTED": "The historical response failed candle validation. Open its quality report.",
    "NO_CANDLES": "No candles were returned. Check the date, market holiday, instrument and historical-data access. No subscription was purchased.",
    "ARCHIVE_LIMIT": "The local archive is full or unavailable. Review private storage before retrying.",
    "KEY_UNAVAILABLE": "Encryption key unavailable or ciphertext unreadable. Restore the separate keyring; credentials were not replaced.",
    "NOT_CONFIGURED": "Save and enable Zerodha settings first.",
    "LOGIN_REQUIRED": "Log in with Zerodha to create a new API session.",
    "SESSION_EXPIRED": "The broker session expired or was revoked. Log in with Zerodha again.",
    "FLOW_INVALID": "Login verification failed or timed out. Start Login with Zerodha again from this browser.",
    "AUTH_FAILED": "Zerodha authentication failed. Check your app configuration and retry interactive login.",
    "NETWORK_ERROR": "Zerodha is temporarily unreachable. Try again later.",
    "RATE_LIMITED": "Zerodha rate limit reached. Wait before trying again.",
    "API_ERROR": "Zerodha could not complete this read-only request. Check permissions and data access.",
    "OPERATION_BLOCKED": "This broker operation is unavailable in research mode.",
    "CONFIG_CHANGED": "Settings changed during login. Start a new login.",
    "INVALID_INPUT": "Invalid market-data request parameters.",
    "DISCONNECT_LOCAL": "Local session removed. Remote revocation could not be confirmed; use Zerodha's logout controls if needed.",
}


class BrokerError(Exception):
    def __init__(self, code):
        self.code = code if code in MESSAGES else "API_ERROR"
        super().__init__(MESSAGES[self.code])
