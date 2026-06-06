from __future__ import annotations

from dataclasses import dataclass

from dashsys_agent.config import Settings


@dataclass(frozen=True)
class CredentialStatus:
    present: bool
    missing: list[str]
    sandbox: str


def validate_real_api_credentials(settings: Settings) -> list[str]:
    missing = []
    for name, value in {
        "ADOBE_CLIENT_ID": settings.adobe_client_id,
        "ADOBE_CLIENT_SECRET": settings.adobe_client_secret,
        "ADOBE_IMS_ORG": settings.adobe_ims_org,
        "ADOBE_SANDBOX": settings.adobe_sandbox,
    }.items():
        if not value:
            missing.append(name)
    return missing


def credential_status(settings: Settings) -> CredentialStatus:
    missing = validate_real_api_credentials(settings)
    return CredentialStatus(
        present=not missing,
        missing=missing,
        sandbox=settings.adobe_sandbox,
    )
