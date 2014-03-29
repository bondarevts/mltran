#!/usr/bin/env python
# -*- coding: utf8 -*-
import contextlib

import sys
import requests

from lxml import etree
from subprocess import Popen, PIPE


class LessPipe:
    def __init__(self):
        self.p = Popen('less', stdin=PIPE)

    def write(self, strings):
        """
        Print list or one string into less pipe
        """
        if isinstance(strings, list):
            strings = '\n'.join(strings)
        self.p.stdin.write(strings)

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def make_request(word):
    request_address = 'http://www.multitran.ru/c/m.exe'
    response = requests.get(request_address, params={'s': word})
    print(response.url)
    code = etree.HTML(response.text.encode('cp1252').decode('cp1251'))
    # doc = etree.ElementTree(code)
    #
    # result = etree.tostring(code, pretty_print=True, method="html", encoding='unicode')
    # print(result)

    results_xpath = '/html/body/table/tr/td[2]/table/tr/td/table/tr[2]/td/table/tr/td[2]/table[2]'

    results = [entry.text.encode('utf-8') for entry in code.xpath(results_xpath + '/tr/td[2]/a')]

    with open('unsorted_queries.txt', mode='a') as query_store:
        query_store.write(word + '\n')

    with contextlib.closing(LessPipe()) as less:
        less.write(response.url + '\n')
        less.write(results)


def main():
    if len(sys.argv) == 1:
        print("Usage:\n\t" + sys.argv[0] + " <word>")
        exit(0)

    word = ' '.join(sys.argv[1:])
    make_request(word)


if __name__ == '__main__':
    main()
