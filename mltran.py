#!/usr/bin/env python3

import sys
import requests
import contextlib

from lxml import etree
from subprocess import Popen, PIPE
from collections import namedtuple


langs = {
    'en': 1,
    'ru': 2,
    'de': 3,
    'fr': 4,
    'it': 23,
}


class LessPipe:
    def __init__(self):
        self.p = Popen('less', stdin=PIPE)

    def writelines(self, strings):
        self.write('\n'.join(strings))

    def write(self, string: str):
        self.p.stdin.write(str(string).encode())

    def writeline(self, string=u''):
        self.write(string)
        self.write(u'\n')

    def close(self):
        self.p.stdin.close()
        self.p.wait()


Translation = namedtuple('Translation', ['word', 'categories'])
Link = namedtuple('Link', ['description', 'url'])
Comment = namedtuple('Comment', ['text', 'author'])


class TranslatedEntry:
    def __init__(self, value, part_of_speech, phonetic):
        self.value, self.part_of_speech, self.phonetic = value, part_of_speech, phonetic

    def __str__(self):
        result = u'====== {}'.format(self.value)
        result += u' {}'.format(self.phonetic) if self.phonetic else u''
        result += u' {}'.format(self.part_of_speech) if self.part_of_speech is not None else u''
        result += u' ====='
        return result


class Category:
    def __init__(self, name, words):
        self.name, self.words = name, words

    def __str__(self):
        result = u'\tКатегория: {}\n'.format(self.name)
        result += u'\n'.join(map(str, self.words))
        return result


class TranslationEntry:
    def __init__(self, value, prev_context=None, context=None, comment=None, author=None, link=None):
        self.value, self.prev_context, self.context, self.comment, self.author, self.link = \
            value, prev_context, context, comment, author, link

    def __str__(self):
        result = u''
        result += u'[{}] '.format(self.prev_context.strip(u' ()')) if self.prev_context else u''
        result += self.value
        result += u' [{}]'.format(self.context.strip(u' ()')) if self.context else u''
        result += u' /* {} @{} */'.format(self.comment.text.strip(u' ()'), self.comment.author) if self.comment else u''
        result += u' {{{} ({})}}'.format(self.link.description, self.link.url) if self.link else u''
        result += u' @{}'.format(self.author) if self.author else u''
        return result


class Mltran:
    def __init__(self, word, log=True, log_filename='unsorted_queries.txt', lang='en'):
        if log:
            with open(log_filename, mode='a') as query_store:
                query_store.write(word + '\n')

        request_address = 'http://www.multitran.ru/c/m.exe'
        self.response = requests.get(request_address, params={
            's': word,
            'l1': langs[lang],
            'l2': langs['ru'],
        })
        self.response.encoding = 'utf-8'
        self.response_text = self.response.text.replace('&nbsp;', ' ')

    def url(self):
        return self.response.url

    @staticmethod
    def _is_new_word_row(elem):
        return elem.find('td[@class="gray"]') is not None

    @staticmethod
    def _get_translated_entry(row):
        row_data = row.find('td[@class="gray"]')
        value = row_data.find('a[1]').text
        part_of_speech = row_data.find('em').text
        phonetic = row_data.find('span[@style="color:gray"]')
        if phonetic is not None:
            phonetic = phonetic.text
        return TranslatedEntry(value, part_of_speech, phonetic)

    @staticmethod
    def _get_category(row):
        return row.find('td[1]/a').get('title') or row.find('td[1]/a/i').text  # if first == None return second

    @staticmethod
    def _extend_context(context, text):
        if context:
            return context + u'; ' + text
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
        code = etree.HTML(self.response_text)
        results_xpath = '//div[@class="middle_col"]/table[1]'

        translated_word = None
        categories = []
        for row in code.xpath(results_xpath)[0].findall('.//tr'):
            if row.find('td[@class]') is None:
                continue
            if self._is_new_word_row(row):
                if translated_word:
                    yield Translation(translated_word, categories)
                categories = []
                translated_word = self._get_translated_entry(row)
            else:
                categories.append(Category(self._get_category(row), self._get_translation_entries(row)))
        if translated_word:
            yield Translation(translated_word, categories)


def make_request(word, lang):
    request = Mltran(word, log=False, lang=lang)
    print('url: ' + request.url())
    with contextlib.closing(LessPipe()) as less:
        less.write('url: ' + request.url() + '\n')
        for result in request.results():
            less.writeline(result.word)
            for category in result.categories:
                less.writeline(category)
                less.writeline()


def main():
    if len(sys.argv) == 1:
        print("Usage:\n\t" + sys.argv[0] + " <word>")
        exit(0)

    if len(sys.argv) > 2 and sys.argv[1].startswith('-'):
        lang = sys.argv[1][1:].lower()
        word = ' '.join(sys.argv[2:])
    else: 
        lang = 'en'
        word = ' '.join(sys.argv[1:])

    try:
        word = word.encode('cp1251')
    except UnicodeEncodeError:
        word = word.encode('ascii', 'xmlcharrefreplace')

    try:
        make_request(word, lang)
    except requests.ConnectionError:
        print('Network error! Check your internet connection and try again.')


if __name__ == '__main__':
    main()
