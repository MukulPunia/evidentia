import pytest

from backend.main import parse_quantity_t


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20 t", 20.0),
        ("20 tonnes", 20.0),
        ("20.5 metric tons", 20.5),
        ("20,000 kg", 20.0),
        ("0 kg", 0.0),
    ],
)
def test_claim_quantity_is_read_as_tonnes(raw, expected):
    assert parse_quantity_t(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "twenty tonnes", "-2 t", "10 litres"])
def test_invalid_claim_quantity_has_clear_error(raw):
    with pytest.raises(ValueError):
        parse_quantity_t(raw)
