from string_utils import reverse_words

def test_reverse_words_basic():
    assert reverse_words("hello world") == "world hello"

def test_reverse_words_multiple():
    assert reverse_words("foo bar baz") == "baz bar foo"

def test_reverse_words_single():
    assert reverse_words("single") == "single"

def test_reverse_words_whitespace_only():
    assert reverse_words("   ") == ""

def test_reverse_words_with_extra_spaces():
    assert reverse_words("  hello world  ") == "world hello"

def test_reverse_words_does_not_reverse_characters():
    assert reverse_words("abc def") != "fed cba"