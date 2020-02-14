from lxml.html import builder as html

from mltran import Comment
from mltran import Context
from mltran import Meaning
from mltran import parse_meanings

SEPARATOR = '; '


def _context(value='(', author=None, comment=None):
    args = [value]

    if author is not None:
        args.append(_author(author))
        args.append(')')

    if comment is not None:
        if args[-1] == ')':
            args.insert(-1, _comment(*comment))
        else:
            args.append(_comment(*comment))
    return html.SPAN(*args)


def _comment(text, author):
    return html.SPAN(
        text,
        _author(author),
        style='color:rgb(60,179,113)',
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


def test_meaning_contexts():
    code = html.TD(
        _context('pre context'),
        _meaning('meaning'),
        _context('post context'),
    )
    assert_meaning(code, elements=[
        Context('pre context'),
        'meaning',
        Context('post context'),
    ])


def test_meaning_author():
    code = html.TD(
        _meaning('meaning'),
        _context(author='author'),
    )
    assert_meaning(code, elements=[
        'meaning',
        Context(author='author'),
    ])


def test_strip_context_parenthesis_and_extra_spaces():
    code = html.TD(
        _context(' context\xa0'),
        _meaning('meaning'),
        _context('(test)'),
    )
    assert_meaning(code, elements=[
        Context('context'),
        'meaning',
        Context('test'),
    ])


def test_split_translation():
    code = html.TD(
        _meaning('meaning start'),
        _context('explanation'),
        _meaning('meaning end'),
    )
    assert_meaning(code, elements=[
        'meaning start',
        Context('explanation'),
        'meaning end',
    ])


def test_comment():
    code = html.TD(
        _meaning('meaning'),
        _context('context', comment=('comment', 'author'))
    )
    assert_meaning(code, elements=[
        'meaning',
        Context('context', comment=Comment('comment', 'author'))
    ])
