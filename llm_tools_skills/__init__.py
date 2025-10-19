from .toolbox import Skills
import llm
from typing import Any

@llm.hookimpl
def register_tools(register: Any) -> None:
    register(Skills)
