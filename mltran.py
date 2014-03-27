#!/usr/bin/env python
# -*- coding: utf8 -*-

import sys
import requests

from lxml import etree


from subprocess import Popen, PIPE
import errno


def print_to_less(strings):
    p = Popen('less', stdin=PIPE)
    for s in strings:
        try:
            p.stdin.write(s)
        except IOError as e:
            if e.errno == errno.EPIPE or e.errno == errno.EINVAL:
                # Stop loop on "Invalid pipe" or "Invalid argument".
                # No sense in continuing with broken pipe.
                break
            else:
                # Raise any other error.
                raise

    p.stdin.close()
    p.wait()


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

    results = [entry.text.encode('utf-8') + '\n' for entry in code.xpath(results_xpath + '/tr/td[2]/a')]
    print_to_less(results)
    # print(etree.tostring(entry, pretty_print=True, method="html", encoding='unicode'))


def main():
    word = sys.argv[1]
    make_request(word)


if __name__ == '__main__':
    main()
