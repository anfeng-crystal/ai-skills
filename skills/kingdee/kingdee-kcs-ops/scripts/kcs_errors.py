"""Shared controlled failure type for plan, transport and response boundaries."""


class KcsOpsError(RuntimeError):
    pass



def fail(message: str) -> None:
    raise KcsOpsError(message)
