# encoding=utf-8

"""
bias相关的类
"""
import logging
import time

from data_source.Data_Sub import get_k_data_jq
from data_source.auth_info import jq_login
from data_source.stk_data_class import StkData
from my_config.log import MyLog
from pylab import plt
from sdk.MyTimeOPT import get_current_datetime_str
import jqdatasdk as jq
logger_eml = MyLog('bias_eml', console_level=logging.INFO).logger
logger = MyLog('bias', file_level=logging.WARNING, console_level=logging.INFO).logger
import json
import os
import numpy as np


class Bias(StkData):
    def __init__(self, stk_code, freq, hist_count=2000, span_q=3, span_s=15, local_data_dir='./'):
        super().__init__(stk_code, freq)
        self.hist_count = hist_count
        self.span_s = span_s
        self.span_q = span_q
        self.local_data_dir = local_data_dir
        self.freq = freq
        self.stk_code = stk_code

        self.bias_history_data = {}
        self.json_file_name = self.local_data_dir + \
                   'bias' + \
                   self.stk_code + \
                    '_' + self.freq + \
                   '_' + \
                   str(self.span_q) + \
                   '_' + str(self.span_s) + \
                   '.json'
        
        self.log = ''
        self.rt_bias_compare_data = None
        self.bias_col = 'bias_'+str(span_q)+ '_' +str(span_s)
        
        # 初始化bias数据，如果本地文件有，则直接读取，否则现场制作，并存入本地
        if not self.load_bias_from_json():
            self.save_hist_data()

        # 初始化rt计算对比数据
        self.init_rt_bias_compare_data()
        
    def init_rt_bias_compare_data(self):
        
        self.init_today_minute_data(count=self.span_s + 40)

    def update_rt_bias_compare_data(self, rt_p, rt):
        
        self.update_rt_minute_data(rt_p, rt=rt)
        self.rt_bias_compare_data = self.rt_minute_data

    def add_bias_rank_public(self, df, span_q, span_s):
        """
        供外部调用的公共函数，因此最后没有“去除空值行”的操作
        :param df:
        :param span_q:
        :param span_s:
        :return:
        """
        df.loc[:, 'line_q'] = df['close'].rolling(window=span_q).mean()
        df.loc[:, 'line_s'] = df['close'].rolling(window=span_s).mean()
    
        df.loc[:, self.bias_col] = df.apply(lambda x: x['line_q'] - x['line_s'], axis=1)

        # 计算排名
        df = StkData.add_rank_to_col_smart_public(df, self.bias_col)
        
        return df
        
    def save_hist_data(self):
        """
        在内存测试时，应该先运行此函数，此函数会向类的成员变量self.data中注入数据!
        将历史bias数据保存到本地
        :return:
        """
        df = get_k_data_jq(stk=self.stk_code, freq=self.freq, count=self.hist_count)
        self.data = self.add_bias_rank_public(df, self.span_q, self.span_s)
        self.bias_history_data = self.data[self.bias_col].values
        self.save_bias_to_json()
   
    def save_bias_to_json(self):
        """
        将bias文件的数据存到json文件中
        :param name:
        :return:
        """
        if not os.path.exists(self.local_data_dir):
            os.makedirs(self.local_data_dir)
            
        with open(self.json_file_name, 'w') as f:
            json.dump(list(self.bias_history_data), f)
            
    def load_bias_from_json(self):
        """
        从json文件中读取bias数据
        :return:
        """
        if os.path.exists(self.json_file_name):
            try:
                with open(self.json_file_name, 'r') as f:
                    self.bias_history_data = json.load(f)
                    logger_eml.debug('bias本地历史数据加载成功！')
                    return True
            except Exception as e:
                logger_eml.exception('%s:bias本地历史数据加载失败！原因：\n%s' % (str(self.stk_code), str(e)))
                return False
        else:
            logger_eml.warning('%s:bias没有历史数据！' % str(self.stk_code))
            return False
        
    def cal_rt_bias(self):
        """
        实时计算bias
        :return:
        """
        m_s = np.mean(self.rt_bias_compare_data.tail(self.span_s).loc[:, 'close'])
        m_q = np.mean(self.rt_bias_compare_data.tail(self.span_q).loc[:, 'close'])
        return m_q - m_s
    
    def cal_rt_bias_rank(self, rt_p, rt=False):
        try:
            # 更新对比数据
            self.update_rt_bias_compare_data(rt_p, rt=rt)
            
            bias_rt = self.cal_rt_bias()
            amount_min = list(filter(lambda x: x < bias_rt, self.bias_history_data))
            rt_bias_rank = len(amount_min)/len(self.bias_history_data)
            logger.info('%s：计算得到的bias实时rank为：%0.3f；当前p：%s' % (self.stk_code, rt_bias_rank, str(rt_p)))
            return rt_bias_rank
        except Exception as e_:
            logger_eml.exception('%s：bias计算出错！原因：\n%s' % (self.stk_code, str(e_)))
            return 0.5
    
    def average_line_compensates(self):
        """
        乖离度是判断股价偏离很重要的指标，但是仅此不够，若是单纯使用乖离度判断，
        可能在乖离度很大的地方进行操作，后续不见得有较好收益，因为还有趋势的问题。

        比如，均线在大斜度向下走的时候，如果我们在负向乖离度很高的时候入场，那么很有可能没有任何盈利空间，
        因为后续乖离度恢复正常不是因为价格的反弹，而是随着时间推移，价格下降导致的。

        以房价举例，在房价大幅下跌的时候，我们在房价急速下跌，偏离均线很大的地方入手，后续不见得短期房价会反弹，
        很有可能是房价慢慢下跌到了我们入手的价格，导致乖离度的恢复。

        所以，我们应该使用均线的斜度来修正乖离度指标。

        思路：使用某种均线的斜度，在历时数据中的排名进行补偿！
        :return:
        """

        # 向乖离度数据中增加均线
        self.add_mean_col('close', self.span_s)

        # 计算当前斜率
        self.cal_diff_col('close_m' + str(self.span_s))

        # 对斜率进行排名
        self.add_col_rank('close_m' + str(self.span_s) + '_diff')

        # 斜率排名减去50，让中心点落在0点附近
        self.data['close_m' + str(self.span_s) + '_diff_rank_base0'] = self.data.apply(lambda x:x['close_m' + str(self.span_s) + '_diff_rank']-0.5, axis=1)

        # 根据斜率对bias进行补偿
        self.data['bias_rank_modify'] = self.data.apply(lambda x: x['bias_rank'] - x['close_m' + str(self.span_s) + '_diff_rank_base0'], axis=1)

    def plot_test(self):
        """
        用以测试效果
        :return:
        """
        # self.average_line_compensates()
        df_bias = self.data
        df_bias.loc[:, 'num'] = range(len(df_bias))
        df_bias.plot('num', ['close', self.bias_col, self.bias_col + '_rank'], subplots=True, style='*--')
        
    def update_rt_rank_compare(self, rt_p):
        pass


if __name__ == '__main__':
    jq.auth('18300210801', 'Ypw@522109')

    stk = 'M2101.XDCE'

    bias_obj_1d = Bias(stk_code=stk, freq='1m', span_q=1, span_s=10, hist_count=3600)
    bias_obj_1d.save_hist_data()

    """
    bias_obj_1d.plot_test()
    plt.show()
    
    """
    
    while True:
        rt_p = get_rt_price(stk)
        print('实时排名为：%0.3f' % bias_obj_1d.cal_rt_bias_rank(rt_p, rt=True))
        time.sleep(2)

