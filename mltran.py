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


Translation = namedtuple('Translation', ['word', 'translation_items'])
Translated = namedtuple('Translated', ['value', 'part_of_speech'])
TranslationItem = namedtuple('TranslationItem', ['group', 'words'])
Link = namedtuple('Link', ['description', 'url'])


class Word:
    def __init__(self, value, prev_context=None, context=None, comment=None, author=None, link=None):
        self.value = value
        self.prev_context = prev_context
        self.context = context
        self.comment = comment
        self.author = author
        self.link = link

    def __unicode__(self):
        result = u''
        if self.prev_context:
            result += u'[' + self.prev_context.strip(u' ()') + u'] '
        result += self.value
        if self.context:
            result += u' [' + self.context.strip(u' ()') + u']'
        if self.comment:
            result += u' /* ' + self.comment.strip(u' ()') + u' */'
        if self.link:
            result += u' {' + self.link.description + u' (' + self.link.url + u')}'
        if self.author:
            result += u' @' + self.author
        return result


class Mltran:
    def __init__(self, word, log=True, log_filename='unsorted_queries.txt'):
        if log:
            with open(log_filename, mode='a') as query_store:
                query_store.write(word + '\n')

        request_address = 'http://www.multitran.ru/c/m.exe'
        self.response = requests.get(request_address, params={'s': word})
        self.response.encoding = 'cp1251'

    def url(self):
        return self.response.url

    def text(self):
        return self.response.text

    @staticmethod
    def is_new_word_row(elem):
        return elem.find('td[@bgcolor]') is not None

    @staticmethod
    def get_translated_from_row(row):
        return Translated(row.find('td[@bgcolor]/a[1]').text, row.find('td[@bgcolor]/em').text)

    @staticmethod
    def get_category(row):
        return row.find('td[1]/a').get('title') or row.find('td[1]/a/i').text  # if first == None return second

    @staticmethod
    def get_word_translations(row):
        value = prev_context = context = comment = author = link = None
        words = []
        for elem in row.xpath('td[2]//*'):
            if elem.find('tr/td[@bgcolor]') is not None:
                break
            if elem.tag == 'a':
                if '&&UserName=' in elem.get('href'):
                    author = elem.find('i').text
                elif elem.get('target') == '_blank':
                    link = Link(description=elem.find('i').text, url=elem.get('href'))
                else:
                    value = elem.text

            elif elem.tag == 'span':
                if elem.get('style') == 'color:gray':
                    text = elem.text
                    if text != ' (' and text != ')':
                        if value:
                            context = text
                        else:
                            prev_context = text
                elif elem.get('style') == 'color:black':  # and text == ';  '
                    if value:
                        words.append(Word(value, prev_context, context, comment, author, link))
                        value = prev_context = context = comment = author = link = None
        if value:
            words.append(Word(value, prev_context, context, comment, author, link))
        return words

    def results(self):
        code = etree.HTML(self.text())
        results_xpath = '/html/body/table/tr/td[2]/table/tr/td/table/tr[2]/td/table/tr/td[2]/table[2]'

        translated_word = None
        translation_items = []
        for row in code.xpath(results_xpath)[0].findall('.//tr'):
            if self.is_new_word_row(row):
                if translated_word:
                    yield Translation(translated_word, translation_items)
                translation_items = []
                translated_word = self.get_translated_from_row(row)
            else:
                translation_items.append(TranslationItem(self.get_category(row), self.get_word_translations(row)))
        if translated_word:
            yield Translation(translated_word, translation_items)


def make_request(word):
    request = Mltran(word, log=False)
    print(request.url())
    with contextlib.closing(LessPipe()) as less:
        less.write(request.url() + '\n')
        for result in request.results():

            less.write(u'===== {}, {} =====\n'.format(result.word.value, result.word.part_of_speech))
            for group in result.translation_items:
                less.write(u'\tКатегория: {}\n'.format(group.group))
                for translation in group.words:
                    less.writeline(translation)
                less.writeline()


def main():
    if len(sys.argv) == 1:
        print("Usage:\n\t" + sys.argv[0] + " <word>")
        exit(0)

    word = ' '.join(sys.argv[1:])
    make_request(word)


if __name__ == '__main__':
    main()
