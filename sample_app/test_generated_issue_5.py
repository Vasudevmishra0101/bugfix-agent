from string_utils import is_palindrome

def test_is_palindrome_ignores_spaces():
    assert is_palindrome("Was it a car or a cat I saw")
    assert is_palindrome("A man a plan a canal Panama")

def test_is_palindrome_case_insensitivity():
    assert is_palindrome("racecar")
    assert is_palindrome("RaceCar")
    assert is_palindrome("RACECAR")

def test_is_palindrome_not():
    assert not is_palindrome("hello")
    assert not is_palindrome("Was it a car or a cat I saw?")