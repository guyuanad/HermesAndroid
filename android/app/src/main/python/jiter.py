"""jiter shim - redirects to jiter_pupy (pure Python) on Android.

This module is placed in the Python path BEFORE site-packages so that
`import jiter` resolves to this shim, which delegates to jiter_pupy.
This is needed because the Rust-compiled jiter has no Android wheel.
"""

from jiter_pupy import *  # noqa: F401,F403
from jiter_pupy import from_json, LosslessFloat  # noqa: F811

__all__ = ["from_json", "LosslessFloat"]
