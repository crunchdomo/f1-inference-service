from app import predictor
from app.train import is_finisher

VALID = dict(driver="hamilton", constructor="mercedes", circuit="silverstone", season=2023)


def test_is_finisher():
    assert is_finisher("Finished")
    assert is_finisher("+1 Lap")
    assert not is_finisher("Accident")
    assert not is_finisher("Engine")


def test_predict_one_returns_probability():
    out = predictor.predict_one(grid=1, **VALID)
    assert 0.0 <= out["podium_probability"] <= 1.0
    assert {"podium_probability", "podium_likely", "circuit_dnf_rate"} <= set(out)


def test_grid_zero_does_not_break():
    # pit-lane start (grid 0) is remapped to the back, not treated as pole
    out = predictor.predict_one(grid=0, **VALID)
    assert 0.0 <= out["podium_probability"] <= 1.0
