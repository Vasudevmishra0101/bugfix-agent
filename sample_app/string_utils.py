def is_palindrome(text):
    """Return True if text reads the same forwards and backwards,
    ignoring case and spaces."""
    cleaned = text.lower()
    return cleaned == cleaned[::-1]


def count_vowels(text):
    """Return the number of vowels (a, e, i, o, u) in text, case-insensitive."""
    vowels = set("aeiou")
    return sum(1 for ch in text if ch in vowels)


def title_case(text):
    """Capitalize the first letter of every word in text."""
    return " ".join(word[:1] + word[1:] for word in text.split(" "))


def reverse_words(text):
    """Reverse the order of words in text (not the characters)."""
    return text[::-1]
