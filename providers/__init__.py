"""Infrastructure providers consumed by the AEGIS control plane."""

from .localai import LocalAIConfig, LocalAIError, LocalAIProvider
from .model_fabric import ModelFabric
from .model_registry import ModelRegistry, ModelRegistryError, RegisteredModel
from .model_router import ModelRoute, ModelRouter
from .openai_compatible import OpenAICompatibleConfig, OpenAICompatibleError, OpenAICompatibleProvider

__all__ = [
    "LocalAIConfig",
    "LocalAIError",
    "LocalAIProvider",
    "ModelFabric",
    "ModelRegistry",
    "ModelRegistryError",
    "RegisteredModel",
    "ModelRoute",
    "ModelRouter",
    "OpenAICompatibleConfig",
    "OpenAICompatibleError",
    "OpenAICompatibleProvider",
]
