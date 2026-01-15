from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSettings:
    tolerance_eur: float = 0.05
    max_k_lignes_non_rc: int = 6
    max_lignes_par_tiers: int = 200
    autoriser_multi_rc: bool = True
    max_rc_par_lettrage: int = 2
    max_candidats_par_rc: int = 500


DEFAULT_SETTINGS = ToolSettings()
