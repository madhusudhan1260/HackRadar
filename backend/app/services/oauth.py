"""Google / GitHub sign-in.

Authorization-code flow, hand-rolled with httpx (already a dependency)
rather than a new OAuth library — both providers' endpoints are plain
HTTPS + JSON, so a library buys little here.

Needs real client credentials from each provider's own developer console:
  Google — console.cloud.google.com -> APIs & Services -> Credentials
  GitHub — github.com/settings/developers -> OAuth Apps
Set as env vars. A provider with no credentials configured is simply
absent from configured_providers() — the frontend hides its button, and
/start refuses with a clear error rather than crashing.

CSRF `state` is a signed, timestamped token rather than server-side
session storage — there is no session to store it in before the user is
signed in, and this API has no cookie-based session mechanism at all.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ..config import settings
from ..security import hash_secret, verify_secret

PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scope": "openid email profile",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scope": "read:user user:email",
    },
}

STATE_TTL_SECONDS = 600


@dataclass
class OAuthProfile:
    subject: str
    email: str
    name: str


def _credentials(provider: str) -> tuple[str, str]:
    if provider == "google":
        return settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET
    if provider == "github":
        return settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET
    return "", ""


def configured_providers() -> list[str]:
    return [p for p in PROVIDERS if all(_credentials(p))]


def redirect_uri(provider: str) -> str:
    return f"{settings.OAUTH_REDIRECT_BASE}/api/auth/oauth/{provider}/callback"


def make_state() -> str:
    payload = f"{int(time.time())}"
    return f"{payload}.{hash_secret(payload)}"


def verify_state(state: str) -> bool:
    try:
        payload, sig = state.rsplit(".", 1)
    except ValueError:
        return False
    if not verify_secret(payload, sig):
        return False
    return (time.time() - int(payload)) < STATE_TTL_SECONDS


def authorize_url(provider: str, state: str) -> str:
    client_id, _ = _credentials(provider)
    cfg = PROVIDERS[provider]
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider),
        "scope": cfg["scope"],
        "state": state,
        "response_type": "code",
    }
    if provider == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    return f"{cfg['authorize_url']}?{httpx.QueryParams(params)}"


def exchange_code(provider: str, code: str) -> OAuthProfile:
    """Trade the authorization code for the provider's profile info."""
    client_id, client_secret = _credentials(provider)
    cfg = PROVIDERS[provider]

    with httpx.Client(timeout=15) as client:
        token_resp = client.post(
            cfg["token_url"],
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri(provider),
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise ValueError("Provider did not return an access token")

        if provider == "google":
            info = client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            ).json()
            return OAuthProfile(
                subject=info["sub"], email=info.get("email", ""), name=info.get("name", "")
            )

        # github
        user = client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        ).json()
        email = user.get("email") or ""
        if not email:
            emails = client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            ).json()
            primary = next((e for e in emails if e.get("primary")), None)
            email = (primary or {}).get("email") or (emails[0]["email"] if emails else "")
        return OAuthProfile(
            subject=str(user["id"]), email=email, name=user.get("name") or user.get("login", "")
        )
