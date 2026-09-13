"""Google service-account credentials loader for local and container deployments."""
import json
import os
from pathlib import Path

from google.oauth2.service_account import Credentials

from data.config import GOOGLE_CREDENTIALS


def load_google_credentials(scopes: list[str]) -> Credentials:
    """Load credentials from a mounted file or GOOGLE_CREDENTIALS_JSON."""
    raw_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if raw_json:
        try:
            info = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_CREDENTIALS_JSON noto‘g‘ri JSON") from exc
        return Credentials.from_service_account_info(info, scopes=scopes)

    credentials_path = Path(GOOGLE_CREDENTIALS)
    if not credentials_path.is_file():
        raise FileNotFoundError(
            f"Google service-account fayli topilmadi: {credentials_path}. "
            "GOOGLE_CREDENTIALS yoki GOOGLE_CREDENTIALS_JSON ni sozlang."
        )
    return Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
