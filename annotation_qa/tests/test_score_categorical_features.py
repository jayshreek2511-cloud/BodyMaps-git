import score_stage0


def test_comma_separated_categorical_columns_never_reach_float_probe(monkeypatch):
    original = score_stage0._is_number

    def guarded_is_number(value):
        assert not (isinstance(value, str) and "," in value)
        return original(value)

    monkeypatch.setattr(score_stage0, "_is_number", guarded_is_number)
    rows = [
        {"volume_ml": "12.5", "label_ids_present": "0,1,2,3,5,6",
         "extra_categories": "4,8"},
        {"volume_ml": "13.0", "label_ids_present": "0,1,6,25",
         "extra_categories": "3,9"},
    ]

    features = score_stage0.numeric_features(rows)

    assert features == ["volume_ml"]
    assert "label_ids_present" not in features
