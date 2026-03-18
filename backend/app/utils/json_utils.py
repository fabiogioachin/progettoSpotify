"""Utility per la sanitizzazione dei valori float non-JSON-compliant.

JSON standard non supporta NaN, Infinity, -Infinity.
Questo modulo fornisce una funzione ricorsiva che li sostituisce con None.
"""

import math


def sanitize_nans(obj):
    """Sostituisce ricorsivamente NaN e Infinity con None in dict/list/float.

    Gestisce anche numpy scalar types (np.float64, np.int64, ecc.)
    convertendoli a tipi Python nativi.

    Usage:
        return sanitize_nans({"score": float("nan"), "items": [1.0, float("inf")]})
        # → {"score": None, "items": [1.0, None]}
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_nans(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_nans(item) for item in obj]
    # Handle numpy scalar types (np.float64, np.float32, np.int64, etc.)
    # without importing numpy — check for the .item() method that all numpy scalars have.
    if hasattr(obj, "item"):
        try:
            native = obj.item()
            if isinstance(native, float):
                if math.isnan(native) or math.isinf(native):
                    return None
                return native
            return native
        except (ValueError, TypeError):
            pass
    return obj
