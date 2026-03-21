from __future__ import annotations

from app.product_profiles import apply_product_profile_env

apply_product_profile_env("kernel_robot")

from app.main import app  # noqa: E402

