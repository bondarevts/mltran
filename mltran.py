#!/usr/bin/env python

import io
import sys
import contextlib
from collections import namedtuple
from subprocess import Popen, PIPE

import requests
import click
from lxml import etree


phonetic_alphabet = {
    '[': '[',
    ']': ']',
    '34': '\u02cf',
    '39': '\u00b4',
    '40': '(',
    '41': ')',
    '58': ':',
    '65': '\u028c',
    '68': '\u00f0',
    '69': '\u025c',
    '73': '\u026a',
    '78': '\u014b',
    '79': '\u0254',
    '80': '\u0252',
    '81': '\u0251',
    '83': '\u0283',
    '84': '\u0275',  # ? '\u0298'
    '86': '\u028b',
    '90': '\u0292',
    '97': 'a',
    '98': 'b',
    '100': 'd',
    '101': 'e',
    '102': 'f',
    '103': 'g',
    '104': 'h',
    '105': 'i',
    '106': 'j',
    '107': 'k',
    '108': 'l',
    '109': 'm',
    '110': 'n',
    '112': 'p',
    '113': '\u0259',
    '114': 'r',
    '115': 's',
    '116': 't',
    '117': 'u',
    '118': 'v',
    '119': 'w',
    '120': '\u00e6',
    '122': 'z'
}


languages = {
    'it': 23,
    'de': 3,
    'fr': 4,
    'en': 1
}


def print_to_less(message):
    pipe = Popen('less', stdin=PIPE)
    pipe.stdin.write(message.encode())
    pipe.stdin.close()
    pipe.wait()


Translation = namedtuple('Translation', ['word', 'categories'])
Link = namedtuple('Link', ['description', 'url'])
Comment = namedtuple('Comment', ['text', 'author'])


class TranslatedEntry:
    def __init__(self, value, part_of_speech, phonetic):
        self.value, self.part_of_speech, self.phonetic = value, part_of_speech, phonetic

    def __str__(self):
        result = '====== {}'.format(self.value)
        result += ' {}'.format(self.phonetic) if self.phonetic else ''
        result += ' {}'.format(self.part_of_speech) if self.part_of_speech is not None else ''
        result += ' ====='
        return result


class Category:
    def __init__(self, name, words):
        self.name, self.words = name, words

    def __str__(self):
        result = '\tКатегория: {}\n'.format(self.name)
        result += '\n'.join(str(translation) for translation in self.words)
        return result


class TranslationEntry:
    def __init__(self, value, prev_context=None, context=None,
                 comment=None, author=None, link=None):
        self.value, self.prev_context, self.context, self.comment, self.author, self.link = (
            value, prev_context, context, comment, author, link)

    def __str__(self):
        result = ''
        result += '[{}] '.format(self.prev_context.strip(' ()')) if self.prev_context else ''
        result += self.value
        result += ' [{}]'.format(self.context.strip(' ()')) if self.context else ''
        result += ' /* {} @{} */'.format(self.comment.text.strip(' ()'), self.comment.author) if self.comment else ''
        result += ' {{{} ({})}}'.format(self.link.description, self.link.url) if self.link else ''
        result += ' @{}'.format(self.author) if self.author else ''
        return result


class Mltran:
    def __init__(self, phrase, lang='en'):
        try:
            phrase = phrase.encode('cp1251')
        except UnicodeEncodeError:
            phrase = phrase.encode('ascii', 'xmlcharrefreplace')

        request_address = 'http://www.multitran.ru/c/m.exe'
        self._response = requests.get(request_address, params={
            's': phrase,
            'l1': languages[lang]
        })
        self._response.encoding = 'cp1251'

    @property
    def url(self):
        return self._response.url

    def _text(self):
        return self._response.text

    @staticmethod
    def _is_new_word_row(elem):
        return elem.find('td[@bgcolor]') is not None

    @staticmethod
    def _get_phonetic(row):
        result = ''
        for img in row.findall('td/img'):
            symbol = img.get('src')[5:-4]
            if symbol in phonetic_alphabet:
                result += phonetic_alphabet[symbol]
            else:
                sys.stderr.write('symbol ' + symbol + ' was not found in phonetic table')
        if result:
            return result

    @staticmethod
    def _get_translated_entry(row):
        value = row.find('td[@bgcolor]/a[1]').text
        part_of_speech = row.find('td[@bgcolor]//em')
        if part_of_speech is not None:
            part_of_speech = part_of_speech.text
        phonetic = Mltran._get_phonetic(row)
        return TranslatedEntry(value, part_of_speech, phonetic)

    @staticmethod
    def _get_category(row):
        # if first == None return second
        return row.find('td[1]/a').get('title') or row.find('td[1]/a/i').text

    @staticmethod
    def _extend_context(context, text):
        if context:
            return context + '; ' + text
        return text

    @staticmethod
    def _update_context(context, prev_context, element, value):
        text = element.text
        if text != ' (' and text != ')':
            if value:
                context = Mltran._extend_context(context, text)
            else:
                prev_context = Mltran._extend_context(prev_context, text)
        return context, prev_context

    @staticmethod
    def _get_translation_entries(row):
        value = prev_context = context = comment = author = link = None
        entries = []
        for element in row.xpath('td[2]//*'):
            if element.find('tr/td[@bgcolor]') is not None:
                break
            if element.tag == 'a':
                if not comment and '&&UserName=' in element.get('href'):
                    author = element.find('i').text
                elif element.get('target') == '_blank':
                    link = Link(description=element.find('i').text, url=element.get('href'))
                else:
                    if value:
                        entries.append(TranslationEntry(value, prev_context, context, comment, author, link))
                        prev_context = context = comment = author = link = None
                    value = element.text

            elif element.tag == 'span':
                if element.get('style') == 'color:gray':
                    context, prev_context = Mltran._update_context(context, prev_context, element, value)
                elif element.get('style') == 'color:black' and element.text == ';  ':
                    if value:
                        entries.append(TranslationEntry(value, prev_context, context, comment, author, link))
                        value = prev_context = context = comment = author = link = None
                elif element.get('style') == 'color:rgb(60, 179, 113)':
                    comment = Comment(element.text, element.find('a/i').text)
        if value:
            entries.append(TranslationEntry(value, prev_context, context, comment, author, link))
        return entries

    def results(self):
        code = etree.HTML(self._text())
        results_xpath = '/html/body/table/tr/td[2]/table/tr/td/table/tr[2]/td/table/tr/td[2]/table[2]'

        translated_word = None
        categories = []
        for row in code.xpath(results_xpath)[0].findall('.//tr'):
            if self._is_new_word_row(row):
                if translated_word:
                    yield Translation(translated_word, categories)
                categories = []
                translated_word = self._get_translated_entry(row)
            else:
                categories.append(Category(self._get_category(row), self._get_translation_entries(row)))
        if translated_word:
            yield Translation(translated_word, categories)


def print_request_result(response):
    print('url: {}'.format(response.url))
    for result in response.results():
        print(result.word)
        for category in result.categories:
            print(category)
            print()


@click.command()
@click.argument('words', nargs=-1, required=True)
@click.option('--lang', '-l', default='en', help='Translation language',
              type=click.Choice(languages))
@click.help_option('-h', '--help')
def make_request(words, lang):
    """ Translate word to/from language with multitran.ru """

    # TODO add block less pipe mode
    # TODO add queries logging parameter

    phrase = ' '.join(words)
    request = Mltran(phrase, lang)
    print('url: ' + request.url)
    result_screen = io.StringIO()
    with contextlib.redirect_stdout(result_screen):
        print_request_result(request)
    print_to_less(result_screen.getvalue())


if __name__ == '__main__':
    make_request()
