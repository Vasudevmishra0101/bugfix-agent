from string_utils import count_vowels

def test_count_vowels_lowercase():
    assert count_vowels("hello") == 2
    assert count_vowels("xyz") == 0

def test_count_vowels_uppercase():
    assert count_vowels("HELLO") == 2
    assert count_vowels("AEIOU") == 5
    assert count_vowels("BCDFG") == 0

def test_count_vowels_mixed_case():
    assert count_vowels("HeLLo") == 2
    assert count_vowels("PyThOn") == 1
    assert count_vowels("aEiOu") == 5

def test_count_vowels_empty():
    assert count_vowels("") == 0