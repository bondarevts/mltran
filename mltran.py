#!/usr/bin/env python3
import contextlib
import dataclasses
import io
import sys
from collections import deque
from dataclasses import dataclass
from subprocess import PIPE
from subprocess import Popen
from typing import Iterable
from typing import List
from typing import Optional
from typing import Union

import requests
from lxml import etree

PATCH = False

LANGUAGE_CODES = {
    'en': 1,
    'ru': 2,
}

URL = 'http://www.multitran.ru/c/m.exe'
TABLE_PATH = './/div[@class="middle_col"]/table[1]'


@dataclass
class Comment:
    text: str
    author: str


@dataclass
class Context:
    text: Optional[str] = None
    author: Optional[str] = None
    comment: Optional[Comment] = None

    def __post_init__(self):
        if self.text is not None:
            self.text = self.text.lstrip('(').rstrip(')').strip('\xa0 ')
            if not self.text:
                self.text = None


MeaningPart = Union[Context, str]


@dataclass
class Meaning:
    elements: List[MeaningPart] = dataclasses.field(default_factory=list)

    def add_element(self, element: MeaningPart) -> None:
        self.elements.append(element)


@dataclass
class Topic:
    short_name: Optional[str]
    description: Optional[str]
    meanings: List[Meaning]


@dataclass
class TranslationHeader:
    word: str
    word_class: Optional[str] = None
    pronunciation: Optional[str] = None
    word_prefix: Optional[str] = None


@dataclass
class Translation:
    header: TranslationHeader
    topics: List[Topic]


def show_translations(phrase: str) -> None:
    translations = translate(phrase)
    print_translations(translations)


def translate(phrase: str) -> List[Translation]:
    page_content = load_page(phrase)
    return list(parse_translation_page(page_content))


def load_page(phrase: str) -> str:
    if PATCH:
        import pickle, pathlib
        response = pickle.loads(pathlib.Path('test.pickle').read_bytes())
    else:
        response = requests.get(URL, params={
            's': phrase,
            'l1': LANGUAGE_CODES['en'],
            'l2': LANGUAGE_CODES['ru'],
        })

        import pickle, pathlib
        pathlib.Path('test.pickle').write_bytes(pickle.dumps(response))

    response.encoding = 'utf-8'
    return response.text


def parse_translation_page(page_content: str) -> Iterable[Translation]:
    rows = deque(get_all_rows(page_content))
    while rows and is_separator(rows.popleft()):
        yield parse_translation(rows)


def get_all_rows(page_content: str) -> List[etree.Element]:
    table = etree.HTML(page_content).find(TABLE_PATH)
    return table.findall('tr')


def is_separator(row):
    return row.find('td[@class]') is None


def parse_translation(rows: deque) -> Translation:
    return Translation(
        header=parse_translation_header(rows.popleft()),
        topics=parse_topics(rows),
    )


def parse_translation_header(row) -> TranslationHeader:
    # the header has the following structure:
    # <tr>
    #   <td class="gray">
    #     [<span style="color:gray"> WORD PREFIX </span>]
    #     <a> TRANSLATED WORD </a>
    #     [<span style="color:gray"> PRONUNCIATION </span>]
    #     [<em> WORD CLASS </em>]
    #     [<span class="small"> ... </span>]  # additional unused elements at the end of the header

    translation_header_element = row.find('td[@class="gray"]')
    assert translation_header_element is not None
    header = TranslationHeader(word=translation_header_element.findtext('a'))

    is_prefix = True
    for element in translation_header_element:
        if element.tag == 'a':
            is_prefix = False
            continue

        if element.tag == 'span':
            if is_prefix:
                header.word_prefix = element.text
                is_prefix = False
                continue

            if element.get('style') == 'color:gray':
                header.pronunciation = element.text
                continue

            if element.get('class') == 'small':
                continue

        if element.tag == 'em':
            header.word_class = element.text
            continue

    return header


def parse_topics(rows: deque) -> List[Topic]:
    topics = []
    while rows:
        row = rows.popleft()
        if is_separator(row):
            rows.appendleft(row)
            break
        topics.append(parse_topic(row))
    return topics


def parse_topic(row) -> Topic:
    # The topic has the following structure:
    # <tr>
    #   <td class="subj">
    #     [<a title="TOPIC DESCRIPTION">TOPIC SHORT NAME</a>]
    #   </td>
    #   <td class="trans">
    #      MEANINGS
    # Important notes:
    # * a topic header might be empty:
    #   https://www.multitran.com/m.exe?s=%D0%B8%D0%B7%D0%BC%D0%B5%D0%BD%D1%8F%D1%8E%D1%89%D0%B0%D1%8F%D1%81%D1%8F+%D1%82%D0%B5%D0%BB%D0%B5%D0%B0%D0%BD%D0%B3%D0%B8%D0%BE%D1%8D%D0%BA%D1%82%D0%B0%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F+%D0%B0%D1%82%D0%B0%D0%BA%D1%81%D0%B8%D1%8F&l1=1&l2=2
    topic_element, meanings_element = row
    assert topic_element.get('class') == 'subj'
    assert meanings_element.get('class') == 'trans'
    topic_link = topic_element.find('a')
    return Topic(
        short_name=topic_link.text if topic_link is not None else None,
        description=topic_link.get('title') if topic_link is not None else None,
        meanings=list(parse_meanings(meanings_element)),
    )


def parse_meanings(meanings_element) -> Iterable[Meaning]:
    # Meanings have the following structure:
    # <td>
    #   {meaning elements}
    #   "; "  # separator
    #   ...   # other meanings
    #
    # Meaning elements are the following:
    #   Meaning value:
    #     <a> MEANING </a>
    #
    #   Context:
    #     <span>
    #       ([CONTEXT]
    #       [<i><a> AUTHOR </a></i>]
    #       ["; "
    #       <span style="color:rgb(60,179,113)">
    #         COMMENT
    #         <i><a> AUTHOR </a></i>
    #       </span>
    #       ")"
    #     </span>
    meaning = Meaning()
    for element in meanings_element:
        if element.tag == 'a':
            meaning.add_element(element.text)

        elif element.tag == 'span':
            meaning.add_element(parse_context(element))

        if element.tail == '; ':
            assert meaning.elements
            yield meaning
            meaning = Meaning()
    yield meaning


def parse_context(element) -> Context:
    assert element.tag == 'span'

    context = Context(element.text, author=get_author(element))

    if (comment_element := element.find('span[@style="color:rgb(60,179,113)"]')) is not None:
        comment_text = comment_element.text
        comment_author = get_author(comment_element)
        assert comment_element is not None
        assert comment_author is not None
        context.comment = Comment(comment_text, comment_author)

    return context


def get_author(element) -> Optional[str]:
    author = None
    if (author_element := element.find('i/a')) is not None:
        author = author_element.text
    return author


def print_translations(translations: List[Translation]) -> None:
    for t in translations:
        print_translation_header(t.header)
        print_topics(t.topics)


def print_translation_header(header: TranslationHeader):
    parts = []
    if header.word_prefix is not None:
        parts.append(f'[{header.word_prefix}]')
    parts.append(header.word + ':')
    parts.extend((header.pronunciation, header.word_class))
    print(f' {" ".join(value for value in parts if value is not None)} '.center(60, '='))


def print_topics(topics: List[Topic]) -> None:
    for topic in topics:
        if topic.short_name is None and topic.description is None:
            print('\tБез категории:')
        else:
            print(f'\tКатегория: {topic.short_name} ({topic.description})')
        for meaning in topic.meanings:
            print(format_meaning_in_topic(meaning))
        print()


def format_meaning_in_topic(meaning: Meaning) -> str:
    parts = []
    for element in meaning.elements:
        if isinstance(element, Context):
            parts.append(format_context(element))
        elif isinstance(element, str):
            parts.append(element)
        else:
            raise Exception('Unknown element', element)
    return ' '.join(parts)


def format_context(context: Context) -> str:
    parts = []
    if context.text is not None:
        parts.append(f'{context.text}')
    if context.author is not None:
        parts.append(f'@{context.author}')
    if context.comment is not None:
        parts.append(f'{{{context.comment.text} @{context.comment.author}}}')
    return f'[{" ".join(parts)}]'


@contextlib.contextmanager
def less_utility_pagination():
    result_screen = io.StringIO()
    with contextlib.redirect_stdout(result_screen):
        yield
    print_to_less(result_screen.getvalue())


def print_to_less(message):
    pipe = Popen('less', stdin=PIPE)
    pipe.stdin.write(message.encode())
    pipe.stdin.close()
    pipe.wait()


def main() -> None:
    if len(sys.argv) == 1:
        print(f'Usage:\n\t{sys.argv[0]} <phrase>')
        return

    phrase = ' '.join(sys.argv[1:])

    try:
        with less_utility_pagination():
            show_translations(phrase)
    except requests.ConnectionError:
        print('Network error! Check your internet connection and try again.', file=sys.stderr)


if __name__ == '__main__':
    main()
