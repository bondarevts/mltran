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

    def writelines(self, strings):
        self.write('\n'.join(strings))

    def write(self, string):
        self.p.stdin.write(string)

    def close(self):
        self.p.stdin.close()
        self.p.wait()


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

    def results(self):
        code = etree.HTML(self.text())
        results_xpath = '/html/body/table/tr/td[2]/table/tr/td/table/tr[2]/td/table/tr/td[2]/table[2]'
        return (entry.text.encode('utf-8') for entry in code.xpath(results_xpath + '/tr/td[2]/a'))


def make_request(word):
    request = Mltran(word)
    print(request.url())

    with contextlib.closing(LessPipe()) as less:
        less.write(request.url() + '\n')
        less.writelines(request.results())


def main():
    if len(sys.argv) == 1:
        print("Usage:\n\t" + sys.argv[0] + " <word>")
        exit(0)

    word = ' '.join(sys.argv[1:])
    make_request(word)


if __name__ == '__main__':
    main()
