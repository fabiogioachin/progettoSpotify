"""Test per sanitize_nans utility."""

import json

import numpy as np

from app.utils.json_utils import sanitize_nans


class TestSanitizeNans:
    """Test che NaN, Infinity e numpy scalars vengono sanitizzati."""

    def test_nan_replaced_with_none(self):
        assert sanitize_nans(float("nan")) is None

    def test_inf_replaced_with_none(self):
        assert sanitize_nans(float("inf")) is None

    def test_neg_inf_replaced_with_none(self):
        assert sanitize_nans(float("-inf")) is None

    def test_normal_float_unchanged(self):
        assert sanitize_nans(3.14) == 3.14

    def test_zero_unchanged(self):
        assert sanitize_nans(0.0) == 0.0

    def test_int_unchanged(self):
        assert sanitize_nans(42) == 42

    def test_string_unchanged(self):
        assert sanitize_nans("hello") == "hello"

    def test_none_unchanged(self):
        assert sanitize_nans(None) is None

    def test_bool_unchanged(self):
        assert sanitize_nans(True) is True

    def test_dict_with_nan(self):
        result = sanitize_nans({"a": 1.0, "b": float("nan"), "c": "text"})
        assert result == {"a": 1.0, "b": None, "c": "text"}

    def test_list_with_nan(self):
        result = sanitize_nans([1.0, float("nan"), float("inf"), 2.0])
        assert result == [1.0, None, None, 2.0]

    def test_nested_dict_with_nan(self):
        data = {
            "level1": {
                "level2": {
                    "value": float("nan"),
                    "ok": 1.0,
                }
            },
            "list": [{"x": float("inf")}],
        }
        result = sanitize_nans(data)
        assert result["level1"]["level2"]["value"] is None
        assert result["level1"]["level2"]["ok"] == 1.0
        assert result["list"][0]["x"] is None

    def test_tuple_treated_as_list(self):
        result = sanitize_nans((1.0, float("nan")))
        assert result == [1.0, None]

    def test_numpy_float64_nan(self):
        result = sanitize_nans(np.float64("nan"))
        assert result is None

    def test_numpy_float64_normal(self):
        result = sanitize_nans(np.float64(3.14))
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-10

    def test_numpy_int64(self):
        result = sanitize_nans(np.int64(42))
        assert result == 42

    def test_numpy_float64_inf(self):
        result = sanitize_nans(np.float64("inf"))
        assert result is None

    def test_result_is_json_serializable(self):
        """The whole point: after sanitize_nans, json.dumps must not raise."""
        data = {
            "score": float("nan"),
            "points": [
                {"x": float("inf"), "y": float("-inf")},
                {"x": 1.0, "y": 2.0},
            ],
            "variance": [float("nan"), 0.5],
            "name": "test",
            "count": 10,
        }
        result = sanitize_nans(data)
        # This must not raise ValueError
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["score"] is None
        assert parsed["points"][0]["x"] is None
        assert parsed["points"][1]["x"] == 1.0
        assert parsed["variance"][0] is None
        assert parsed["variance"][1] == 0.5

    def test_numpy_array_in_dict(self):
        """numpy arrays inside dicts should have their elements sanitized."""
        # After .tolist(), numpy arrays become Python lists — test that path
        arr = np.array([1.0, float("nan"), 3.0])
        data = {"values": arr.tolist()}
        result = sanitize_nans(data)
        assert result["values"] == [1.0, None, 3.0]

    def test_empty_structures(self):
        assert sanitize_nans({}) == {}
        assert sanitize_nans([]) == []

    def test_realistic_taste_map_response(self):
        """Simulates a real taste_map response with NaN from PCA."""
        response = {
            "points": [
                {"id": "abc", "x": 1.23, "y": float("nan")},
                {"id": "def", "x": float("inf"), "y": -0.5},
            ],
            "variance_explained": [float("nan"), 0.15],
            "feature_mode": "genre_popularity",
            "genre_groups": {"rock": 5, "pop": 3},
        }
        result = sanitize_nans(response)
        # Must be JSON-serializable
        json.dumps(result)
        assert result["points"][0]["y"] is None
        assert result["points"][1]["x"] is None
        assert result["variance_explained"][0] is None
        assert result["variance_explained"][1] == 0.15
