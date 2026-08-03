"""Tests for mattermill assets — seeded signature and stamp images.

`assets` survives the release trim because the emitters use it: bill_of_sale,
diligence, nj_birth and vintage all draw wet-ink signatures and received
stamps. The longdoc compositors these tests used to sit beside did not, and
went with the rest of the pre-registry forge.
"""

from __future__ import annotations

from mattermill import assets


def test_signature_deterministic_and_varies():
    assert assets.signature_png(1) == assets.signature_png(1)
    assert assets.signature_png(1) != assets.signature_png(2)
    assert assets.signature_png(1)[:8] == b"\x89PNG\r\n\x1a\n"


def test_stamp_deterministic_and_text_fits():
    a = assets.stamp_png(4, lines=["Filed", "Apr 28 2026", "Clerk, U.S. Bankruptcy Court"])
    assert a == assets.stamp_png(4, lines=["Filed", "Apr 28 2026",
                                           "Clerk, U.S. Bankruptcy Court"])
    assert a[:8] == b"\x89PNG\r\n\x1a\n"
