from gemini import GeminiClient, ChatSession


def test_package_exports():
    assert GeminiClient is not None
    assert ChatSession is not None
