# encoding=utf-8

"""
trade 时间判断
"""
import datetime

from data_source.futures_data import FuturesData
from my_config.global_setting import root_path
from sdk.pickle_save_sub import load_p
from my_config.log import MyLog
logger = MyLog('trade_timespan_judge').logger

class TradeTimeSpanJudge:
    def __init__(self):
        self.trade_timespan = load_p(load_location=root_path + '/data_source/LocalData/local_data_save/', file_name='futures_trade_timespan')

    def futures_trade_timespan_judege(self, stk_code):

        # 获取时间段
        kind = FuturesData.get_futures_kind(stk_code)
        t_s_f = list(filter(lambda x: x['kind'] == kind, self.trade_timespan))

        if len(t_s_f) == 0:
            logger.debug('%s品种未能查询到td时段，默认不在td中！' % str(stk_code))
            return False
        else:
            t_s = t_s_f[0]

        # 判断当前是否处于时间段
        in_time = False
        for ts in t_s['time_span']:
            m_now = datetime.datetime.now().hour*60 + datetime.datetime.now().minute
            m_start = ts[0].hour*60 + ts[0].minute
            m_end = ts[1].hour*60 + ts[1].minute
            if (m_start <= m_now) & (m_now <= m_end):
                in_time = True

        return in_time


if __name__ == '__main__':

    ttsj = TradeTimeSpanJudge()
    r = ttsj.futures_trade_timespan_judege('"M2101.XDCE"')
    end = 0