"""Base tool contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class AgentTool(ABC, Generic[InputT, OutputT]):
    name: str

    @abstractmethod
    def run(self, payload: InputT) -> OutputT:
        raise NotImplementedError

