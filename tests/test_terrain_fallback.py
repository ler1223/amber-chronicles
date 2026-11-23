"""Запасные операции земли без scipy: Mac/Anaconda часто ломает ABI numpy/scipy."""
import numpy as np

from deck import terrain as TR


def test_distance_zoom_and_uniform_fallbacks(monkeypatch):
    monkeypatch.setattr(TR, "ndimage", None)
    mask = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=bool)
    d = TR._distance(mask)
    assert d.shape == mask.shape and d[1, 1] > 0 and d[0, 0] == 0
    a = np.array([[1, 2], [3, 4]], dtype=np.float32)
    z = TR._zoom(a, 2)
    assert z.shape == (4, 4) and z[0, 0] == 1 and z[0, 2] == 2 and z[2, 0] == 3
    flat = np.full((8, 8), 7, dtype=np.float32)
    assert np.allclose(TR._uniform(flat, 5), 7)
