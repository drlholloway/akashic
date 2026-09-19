from .base import Adapter

REGISTRY: dict[str, type[Adapter]] = {}


def register(cls: type[Adapter]) -> type[Adapter]:
    REGISTRY[cls.vendor] = cls
    return cls


def load_all() -> None:
    from . import pedalpcb, aionfx, madbean, guitarpcb, sheepylove, deadendfx, moonn, fivecats, parasit, pcbway, pcbguitarmania, deadastronaut, bentfishbowl, ggg, lectricfx, expanon, zerogiod, otrfx, dirtmonger, maskaudio, effectslayouts, jmk, eae  # noqa: F401
    try:
        from . import fuzzdog  # noqa: F401
    except ImportError:
        pass
