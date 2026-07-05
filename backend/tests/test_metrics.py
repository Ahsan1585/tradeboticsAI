import math
from services.metrics import safe_float, sanitize_nans

def test_safe_float_handles_none():
    assert safe_float(None) == 0.0

def test_safe_float_handles_nan_string():
    assert safe_float("not-a-number") == 0.0

def test_safe_float_handles_custom_default():
    assert safe_float(None, default=-1.0) == -1.0

def test_safe_float_passes_through_valid_number():
    assert safe_float("3.5") == 3.5

def test_sanitize_nans_replaces_nan_in_dict():
    result = sanitize_nans({"a": float("nan"), "b": 1.0})
    assert result == {"a": 0.0, "b": 1.0}

def test_sanitize_nans_recurses_into_lists():
    result = sanitize_nans([{"x": float("inf")}])
    assert result == [{"x": 0.0}]
