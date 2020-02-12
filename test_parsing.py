from lxml.html import builder as html

from mltran import Comment
from mltran import Meaning
from mltran import parse_meanings

SEPARATOR = '; '


def _comment(value='(', author=None):
    if author is None:
        return html.SPAN(value)
    return html.SPAN(
        value,
        _author(author),
        ')',
    )


def _meaning(value):
    return html.A(value)


def _author(name):
    return html.I(html.A(name))


def assert_meaning(code, *, text=None, elements=None):
    meanings = list(parse_meanings(code))
    if text is not None:
        assert meanings == [Meaning([text])]
        return
    if elements is not None:
        assert meanings == [Meaning(elements)]


def test_parse_single_meaning():
    code = html.TD(
        _meaning('meaning'),
    )
    assert_meaning(code, text='meaning')


def test_parse_multiple_meanings():
    code = html.TD(
        _meaning('meaning1'),
        SEPARATOR,
        _meaning('meaning2'),
    )
    assert list(parse_meanings(code)) == [Meaning(['meaning1']), Meaning(['meaning2'])]


def test_meaning_comments():
    code = html.TD(
        _comment('pre comment'),
        _meaning('meaning'),
        _comment('post comment'),
    )
    assert_meaning(code, elements=[
        Comment('pre comment'),
        'meaning',
        Comment('post comment'),
    ])


def test_meaning_author():
    code = html.TD(
        _meaning('meaning'),
        _comment(author='author'),
    )
    assert_meaning(code, elements=[
        'meaning',
        Comment(author='author'),
    ])


def test_strip_comment_parenthesis_and_extra_spaces():
    code = html.TD(
        _comment(' comment\xa0'),
        _meaning('meaning'),
        _comment('(test)'),
    )
    assert_meaning(code, elements=[
        Comment('comment'),
        'meaning',
        Comment('test'),
    ])


def test_split_translation():
    code = html.TD(
        _meaning('meaning start'),
        _comment('explanation'),
        _meaning('meaning end'),
    )
    assert_meaning(code, elements=[
        'meaning start',
        Comment('explanation'),
        'meaning end',
    ])
