from string_utils import title_case

def test_title_case_basic():
    assert title_case("hello world") == "Hello World"

def test_title_case_single_word():
    assert title_case("hello") == "Hello"

def test_title_case_empty():
    assert title_case("") == ""