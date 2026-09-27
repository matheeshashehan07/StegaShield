"""Compatibility package for launching the nested gateway from this workspace.

The distributable project lives in ``stegashield-gateway``. Extending this
package path keeps the README's ``backend.app.main:app`` target valid when the
command is run from the outer checkout directory as well.
"""

from pathlib import Path


_gateway_backend = Path(__file__).resolve().parent.parent / "stegashield-gateway" / "backend"
if _gateway_backend.is_dir():
    __path__.append(str(_gateway_backend))
