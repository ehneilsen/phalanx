"""Pydantic models for Phalanx application secrets."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Extra, Field, SecretStr, validator

__all__ = [
    "ConditionalSecretConfig",
    "ConditionalSecretCopyRules",
    "ConditionalSecretGenerateRules",
    "ResolvedSecret",
    "Secret",
    "SecretConfig",
    "SecretCopyRules",
    "SecretGenerateRules",
    "SecretGenerateType",
]


class SecretCopyRules(BaseModel):
    """Rules for copying a secret value from another secret."""

    application: str
    """Application from which the secret should be copied."""

    key: str
    """Secret key from which the secret should be copied."""

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class ConditionalSecretCopyRules(SecretCopyRules):
    """Possibly conditional rules for copying a secret value from another."""

    condition: str | None = Field(
        None,
        description=(
            "Helm chart value that, if set, indicates the secret should be"
            " copied"
        ),
        alias="if",
    )


class SecretGenerateType(Enum):
    """Type of secret for generated secrets."""

    password = "password"
    gafaelfawr_token = "gafaelfawr-token"
    fernet_key = "fernet-key"
    rsa_private_key = "rsa-private-key"
    bcrypt_password_hash = "bcrypt-password-hash"
    mtime = "mtime"


class SecretGenerateRules(BaseModel):
    """Rules for generating a secret value."""

    type: SecretGenerateType
    """Type of secret."""

    source: str | None = None
    """Key of secret on which this secret is based.

    This may only be set by secrets of type ``bcrypt-password-hash`` or
    ``mtime``.
    """

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid

    @validator("source")
    def _validate_source(
        cls, v: str | None, values: dict[str, Any]
    ) -> str | None:
        secret_type = values["type"]
        want_value = secret_type in (
            SecretGenerateType.bcrypt_password_hash,
            SecretGenerateType.mtime,
        )
        if v is None and want_value:
            msg = f"source not set for secret of type {secret_type}"
            raise ValueError(msg)
        if v is not None and not want_value:
            msg = f"source not allowed for secret of type {secret_type}"
            raise ValueError(msg)
        return v


class ConditionalSecretGenerateRules(SecretGenerateRules):
    """Possibly conditional rules for generating a secret value."""

    condition: str | None = Field(
        None,
        description=(
            "Helm chart value that, if set, indicates the secret should be"
            " generated"
        ),
        alias="if",
    )


class SecretConfig(BaseModel):
    """Specification for an application secret."""

    description: str
    """Description of the secret."""

    copy_rules: SecretCopyRules | None = Field(
        None,
        description="Rules for where the secret should be copied from",
        alias="copy",
    )

    generate: SecretGenerateRules | None = None
    """Rules for how the secret should be generated."""

    value: SecretStr | None = None
    """Secret value."""

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid

    @validator("generate")
    def _validate_generate(
        cls, v: SecretGenerateRules | None, values: dict[str, Any]
    ) -> SecretGenerateRules | None:
        has_copy = "copy" in values and "condition" not in values["copy"]
        if v and has_copy:
            msg = "both copy and generate may not be set for the same secret"
            raise ValueError(msg)
        return v

    @validator("value")
    def _validate_value(
        cls, v: SecretStr | None, values: dict[str, Any]
    ) -> SecretStr | None:
        has_copy = values.get("copy") and "condition" not in values["copy"]
        has_generate = (
            values.get("generate") and "condition" not in values["generate"]
        )
        if v and (has_copy or has_generate):
            msg = "value may not be set if copy or generate is set"
            raise ValueError(msg)
        return v


class ConditionalSecretConfig(SecretConfig):
    """Possibly conditional specification for an application secret.

    This class represents the on-disk schema for secret configurations, which
    may include conditions on the secret itself and on its copy and generate
    rules. Those conditions cannot be evaluated until the configuration of an
    application for a specific environment is known.

    The equivalent class with the conditions evaluated is `SecretConfig`.
    """

    condition: str | None = Field(
        None,
        description=(
            "Helm chart value that, if set, indicates the secret should be"
            " generated"
        ),
        alias="if",
    )

    copy_rules: ConditionalSecretCopyRules | None = Field(
        None,
        description="Rules for where the secret should be copied from",
        alias="copy",
    )

    generate: ConditionalSecretGenerateRules | None = None
    """Rules for how the secret should be generated."""


class Secret(SecretConfig):
    """Specification for an application secret for a specific environment.

    The same as `SecretConfig` except augmented with the secret application
    and key for internal convenience.
    """

    key: str
    """Key of the secret."""

    application: str
    """Application of the secret."""


class ResolvedSecret(BaseModel):
    """A secret that has been resolved for a given application instance.

    Secret resolution means that the configuration has been translated into
    either a secret value or knowledge that the secret is a static secret that
    must come from elsewhere.
    """

    key: str
    """Key of the secret."""

    application: str
    """Application for which the secret is required."""

    value: SecretStr | None = None
    """Value of the secret if known."""

    static: bool = False
    """Whether this is a static secret.

    Static secrets are those whose values come from an external source.
    """
