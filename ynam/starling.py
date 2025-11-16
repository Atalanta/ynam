"""Starling Bank API interactions."""

import os
from datetime import datetime, timedelta
from typing import Optional

import requests


API_BASE_URL = "https://api.starlingbank.com/api/v2"


def get_account_info(token: str) -> tuple[str, str]:
    """Get the primary account UID and default category.

    Args:
        token: OAuth bearer token.

    Returns:
        Tuple of (account_uid, category_uid).

    Raises:
        requests.RequestException: If API request fails.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    response = requests.get(f"{API_BASE_URL}/accounts", headers=headers)
    response.raise_for_status()
    accounts = response.json()["accounts"]
    account = accounts[0]
    return account["accountUid"], account["defaultCategory"]


def get_transactions(token: str, account_uid: str, category_uid: str, since_date: datetime) -> list[dict]:
    """Fetch transactions from Starling Bank API.

    Args:
        token: OAuth bearer token.
        account_uid: Account UID.
        category_uid: Category UID.
        since_date: Fetch transactions from this date onwards.

    Returns:
        List of transaction dictionaries.

    Raises:
        requests.RequestException: If API request fails.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    params = {
        "changesSince": since_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    }

    url = f"{API_BASE_URL}/feed/account/{account_uid}/category/{category_uid}"
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["feedItems"]


def get_account_balance(token: str, account_uid: str) -> int:
    """Get current account balance from Starling Bank API.

    Args:
        token: OAuth bearer token.
        account_uid: Account UID.

    Returns:
        Balance in minor units (pence).

    Raises:
        requests.RequestException: If API request fails.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    response = requests.get(f"{API_BASE_URL}/accounts/{account_uid}/balance", headers=headers)
    response.raise_for_status()
    return int(response.json()["clearedBalance"]["minorUnits"])


def get_token() -> Optional[str]:
    """Get Starling API token from environment.

    Returns:
        Token string or None if not set.
    """
    return os.environ.get("STARLING_TOKEN")
