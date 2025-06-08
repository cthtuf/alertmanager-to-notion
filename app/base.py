import typing as t

from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    from google.cloud.functions_v1.context import Context  # pragma: nocover


class BaseHandler(ABC):
    """Base handler."""

    @abstractmethod
    def __init__(self, event: dict[str, t.Any], context: "Context") -> None:
        """Init handler."""
        raise NotImplementedError()  # pragma: nocover

    @abstractmethod
    def __call__(self) -> None:
        """Execute handler."""
        raise NotImplementedError()  # pragma: nocover
