#!/usr/bin/env python
# -*- coding: utf8 -*-

import sys
import requests
import contextlib

from lxml import etree
from subprocess import Popen, PIPE
from collections import namedtuple


def xml_element_to_string(elem):
    return etree.tostring(elem, pretty_print=True, method="html", encoding='unicode')


phonetic_alphabet = {
    u'[': u'[',
    u']': u']',
    u'34': u'\u02cf',
    u'39': u'\u00b4',
    u'40': u'(',
    u'41': u')',
    u'58': u':',
    u'65': u'\u028c',
    u'68': u'\u00f0',
    u'69': u'\u025c',
    u'73': u'\u026a',
    u'78': u'\u014b',
    u'79': u'\u0254',
    u'80': u'\u0252',
    u'81': u'\u0251',
    u'83': u'\u0283',
    u'84': u'\u0275',  # ? u'\u0298'
    u'86': u'\u028b',
    u'90': u'\u0292',
    u'97': u'a',
    u'98': u'b',
    u'100': u'd',
    u'101': u'e',
    u'102': u'f',
    u'103': u'g',
    u'104': u'h',
    u'105': u'i',
    u'106': u'j',
    u'107': u'k',
    u'108': u'l',
    u'109': u'm',
    u'110': u'n',
    u'112': u'p',
    u'113': u'\u0259',
    u'114': u'r',
    u'115': u's',
    u'116': u't',
    u'117': u'u',
    u'118': u'v',
    u'119': u'w',
    u'120': u'\u00e6',
    u'122': u'z'
}


langs = {
    'it': 23,
    'de': 3,
    'fr': 4,
    'en': 1
}


class LessPipe:
    def __init__(self):
        self.p = Popen('less', stdin=PIPE)

    def writelines(self, strings):
        self.write('\n'.join(strings))

    def write(self, string):
        self.p.stdin.write(unicode(string).encode('utf8'))

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

    def __unicode__(self):
        result = u'====== {}'.format(self.value)
        result += u' {}'.format(self.phonetic) if self.phonetic else u''
        result += u' {}'.format(self.part_of_speech) if self.part_of_speech is not None else u''
        result += u' ====='
        return result


class Category:
    def __init__(self, name, words):
        self.name, self.words = name, words

    def __unicode__(self):
        result = u'\tКатегория: {}\n'.format(self.name)
        result += u'\n'.join(unicode(translation) for translation in self.words)
        return result


class TranslationEntry:
    def __init__(self, value, prev_context=None, context=None, comment=None, author=None, link=None):
        self.value, self.prev_context, self.context, self.comment, self.author, self.link = \
            value, prev_context, context, comment, author, link

    def __unicode__(self):
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
            'l1': langs[lang]
        })
        self.response.encoding = 'cp1251'

    def url(self):
        return self.response.url

    def _text(self):
        return self.response.text

    @staticmethod
    def _is_new_word_row(elem):
        return elem.find('td[@bgcolor]') is not None

    @staticmethod
    def _get_phonetic(row):
        result = u''
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
    word = word.decode('utf8').encode('cp1251')

    try:
        make_request(word, lang)
    except requests.ConnectionError:
        print('Network error! Check your internet connection and try again.')


if __name__ == '__main__':
    main()
