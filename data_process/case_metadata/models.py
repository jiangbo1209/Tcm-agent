"""Re-export of :class:`MedCase` for backwards compatibility.

The canonical definition lives in :mod:`UI.backend.app.models.med_case`.
This module is kept so that legacy imports
(``from data_process.case_metadata.models import MedCase``) keep working.
"""

from __future__ import annotations

from UI.backend.app.models import MedCase

__all__ = ["MedCase"]
