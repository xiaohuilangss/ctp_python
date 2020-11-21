# encoding=utf-8
import pickle
import os


def dump_p(data, save_location, file_name):

    with open(save_location + file_name, 'wb') as f:
        pickle.dump(data, f)                            # 导入数据data到文件f中
        print('save data: %s successful' % save_location + file_name)


def load_p(load_location, file_name):

    with open(load_location + file_name, 'rb') as f:
        return pickle.load(f)           # 读取数据
