# encoding=utf-8

"""
有关数字和字母方面正则化过滤的类

比如，从字符串中提取字母，或者从字符串中提取数字
"""
import re


class NlReFilter:
    def __init__(self):
        pass

    @staticmethod
    def filter_letter_from_str(str_input):
        """
        从字符串中过滤出字母
        :param str_input:
        :return:
        """

        return ''.join(re.findall(r'[A-Za-z]', str_input))

    @staticmethod
    def filter_num_from_str(str_input):
        """
        从字符串中过滤出数字
        :param str_input:
        :return:
        """

        return re.sub("\D", "", str_input)