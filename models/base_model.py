"""
base_model.py
-------------
Minimal protocol that every model file must satisfy.

To implement a new model, create a new .py file in models/ and define:

    NAME        : str            - human-readable model name
    VARIABLES   : list[str]      - names of state variables (e.g. ["prey", "predator"])
    DEFAULT_PARAMS : dict        - default parameter values

    def derivatives(state, t, params) -> list[float]:
        ...

That's all. No class inheritance required.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelProtocol(Protocol):
    """
    Structural protocol used only for type-checking and documentation.
    Model files do NOT need to import or subclass this.
    """

    NAME: str
    VARIABLES: list[str]
    DEFAULT_PARAMS: dict

    def derivatives(
        self, state: list[float], t: float, params: dict
    ) -> list[float]: ...
