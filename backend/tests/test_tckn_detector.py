from backend.app.detectors.tckn_detector import is_valid_tckn


def test_tckn_rejects_zero_first_digit():
    assert is_valid_tckn("01234567890") is False


def test_tckn_rejects_letters():
    assert is_valid_tckn("1234567890A") is False


def test_tckn_rejects_wrong_length():
    assert is_valid_tckn("12345") is False