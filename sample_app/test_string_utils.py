from string_utils import count_vowels, is_palindrome, title_case


def test_is_palindrome():
    assert is_palindrome("racecar")
    assert is_palindrome("Was it a car or a cat I saw")
    assert not is_palindrome("hello")


def test_count_vowels():
    assert count_vowels("hello") == 2
    assert count_vowels("HELLO") == 2
    assert count_vowels("xyz") == 0


def test_title_case():
    assert title_case("hello world") == "Hello World"
