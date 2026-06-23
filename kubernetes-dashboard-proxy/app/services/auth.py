import base64
import json


def decode_jwt(token):
    """Decode JWT payload (without verifying signature)."""
    try:

        _, payload, _ = token.split(".")

        payload += "=" * (-len(payload) % 4)

        data = base64.urlsafe_b64decode(payload)

        return json.loads(data)

    except Exception as e:

        raise ValueError(
            f"Invalid JWT: {e}"
        )


def extract_team_from_sa(sa_name):
    """
    Extract team name from ServiceAccount name.
    Example: dashboard-sre-test -> sre
    """
    parts = sa_name.split("-")

    if len(parts) >= 3:

        return "-".join(parts[1:-1])

    return None