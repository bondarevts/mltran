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
        self.p.stdin.write(string)

    def close(self):
        self.p.stdin.close()
        self.p.wait()


Translation = namedtuple('Translation', ['word', 'translation_items'])
Translated = namedtuple('Translated', ['value', 'part_of_speech'])
TranslationItem = namedtuple('TranslationItem', ['group', 'words'])
Word = namedtuple('Word', ['value', 'context', 'comment', 'author'])


class Mltran:
    def __init__(self, word, log=True, log_filename='unsorted_queries.txt'):
        if log:
            with open(log_filename, mode='a') as query_store:
                query_store.write(word + '\n')

        request_address = 'http://www.multitran.ru/c/m.exe'
        self.response = requests.get(request_address, params={'s': word})

    def url(self):
        return self.response.url

    def text(self):
        return self.response.text.encode('cp1252').decode('cp1251')

    @staticmethod
    def is_new_word_row(elem):
        return elem.find('td[@bgcolor]') is not None

    @staticmethod
    def get_translated_from_row(row):
        return Translated(row.find('td[@bgcolor]/a[1]').text, row.find('td[@bgcolor]/em').text.encode('utf-8'))

    @staticmethod
    def get_group(row):
        return row.find('td[1]/a').get('title').encode('utf-8')

    @staticmethod
    def get_translations(row):
        return [translation.text.encode('utf-8') for translation in row.findall('td[2]/a')]

    def results(self):
        code = etree.HTML(self.text())
        results_xpath = '/html/body/table/tr/td[2]/table/tr/td/table/tr[2]/td/table/tr/td[2]/table[2]'

        translated_word = None
        translation_items = []
        for row in code.xpath(results_xpath)[0].iterchildren():
            if self.is_new_word_row(row):
                if translated_word:
                    yield Translation(translated_word, translation_items)
                translation_items = []
                translated_word = self.get_translated_from_row(row)
            else:
                translation_items.append(TranslationItem(self.get_group(row), self.get_translations(row)))
        if translated_word:
            yield Translation(translated_word, translation_items)


def make_request(word):
    request = Mltran(word, log=False)
    print(request.url())

    with contextlib.closing(LessPipe()) as less:
        less.write(request.url() + '\n')
        for result in request.results():
            less.write('===== {}, {} =====\n'.format(result.word.value, result.word.part_of_speech))
            for group in result.translation_items:
                less.write('\tГруппа: {}\n'.format(group.group))
                for translation in group.words:
                    less.write(translation + '\n')
                less.write('\n')


def main():
    if len(sys.argv) == 1:
        print("Usage:\n\t" + sys.argv[0] + " <word>")
        exit(0)

    word = ' '.join(sys.argv[1:])
    make_request(word)


if __name__ == '__main__':
    main()
