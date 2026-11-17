"""Проверки оптических профилей standalone-проекта."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workshop import optics as O  # noqa: E402


def test_diamond_critical_angle_is_real():
    p = O.profile("diamond")
    assert 24.0 < p["critical_angle"] < 24.8
    assert p["dispersion"] > 0.04
    assert p["birefringence_value"] == 0.0


def test_current_gems_have_numeric_optics():
    for gid in ("ruby", "sapphire", "emerald", "topaz", "amethyst"):
        p = O.profile(gid)
        assert len(p["ior"]) == 3
        assert p["critical_angle"] > 20
        assert 0.0 <= p["birefringence_value"] < 0.1
        assert 0.0 <= p["pleochroism_value"] <= 1.0


def test_emerald_is_more_birefringent_than_quartz():
    assert O.biref_value("emerald") < O.biref_value("zircon")
    assert O.pleo_value("tourmaline") > O.pleo_value("amethyst")
