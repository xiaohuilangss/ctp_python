# encoding=utf-8

"""

获取futures数据的类
"""
import datetime
import math
import time

from data_source.Data_Sub import get_k_data_jq
from my_config.global_setting import root_path
from sdk.MyTimeOPT import convert_np_datetime64_to_datetime
from sdk.pickle_save_sub import dump_p
from sdk.re.re_number_Letters_filter import NlReFilter

import jqdatasdk as jq
import pandas as pd


class FuturesData:
    def __init__(self):
        pass

    @staticmethod
    def get_all_domain():
        """ stk_code, display_name """

        futures_all = jq.get_all_securities(types=['futures'])
        stk_all_mf = futures_all.loc[
                     futures_all.apply(lambda x: NlReFilter.filter_num_from_str(x['name']) in ['9999'], axis=1),
                     :]

        # 将主力转为实际
        for idx in stk_all_mf.index:

            name_str = stk_all_mf.loc[idx, 'name']

            if NlReFilter.filter_num_from_str(name_str) == '9999':
                dmt = jq.get_dominant_future(
                    NlReFilter.filter_letter_from_str(name_str))
                stk_all_mf.loc[idx, 'display_name'] = stk_all_mf.loc[idx, 'display_name'] + dmt
                stk_all_mf.loc[idx, 'dominant'] = dmt

        stk_all_mf.loc[:, 'stk_code'] = stk_all_mf.index
        return stk_all_mf

    def get_kind_condensation(self):
        """
        获取品种缩写
        :return:
        """

        futures_all = self.get_all_domain()
        stk_all_mf = futures_all.loc[
                     futures_all.apply(lambda x: NlReFilter.filter_num_from_str(x['name']) in ['9999'], axis=1),
                     :]

        # 将主力转为实际
        for idx in stk_all_mf.index:

            name_str = stk_all_mf.loc[idx, 'name']
            stk_all_mf.loc[idx, 'kind_condensation'] = NlReFilter.filter_letter_from_str(name_str)

        stk_all_mf.loc[:, 'code'] = stk_all_mf.index
        return stk_all_mf

    @staticmethod
    def get_single_trade_time_span(f_code):

        df = get_k_data_jq(stk=f_code, count=60*20, freq='1m')

        l_group = list(df.groupby(by='date'))
        l_group.sort(key=lambda x: len(x[1]), reverse=True)
        df = l_group[0][1]

        # 获取该天数据
        df.loc[:, 'datetime_dt'] = df.apply(lambda x: convert_np_datetime64_to_datetime(x['datetime']), axis=1)


        df.loc[:, 'num'] = range(0, len(df))
        df.set_index('num')

        df.loc[:, 'dt_next'] = df['datetime_dt'].shift(-1)

        time_span = []
        t_s: datetime.datetime = None
        t_e: datetime.datetime = None

        for idx in df.index:
            t_now: datetime.datetime = df.loc[idx, 'datetime_dt']
            t_next: datetime.datetime = df.loc[idx, 'dt_next']

            if isinstance(t_s, type(None)):
                t_s = t_now
                if t_s.minute % 5 != 0:
                    t_s = t_now - datetime.timedelta(minutes=t_now.minute % 5)

            if pd.isnull(t_next):
                t_e = t_now

            elif t_next.hour * 60 + t_next.minute - (t_now.hour * 60 + t_now.minute) > 1:
                t_e = t_now

            if not isinstance(t_e, type(None)):
                time_span.append((t_s, t_e))
                t_s = None
                t_e = None

        return list(set(time_span))

    def get_futures_trade_date(self):

        # 获取domain
        domain_df = self.get_kind_condensation()

        r_dict = []

        for idx in domain_df.index:
            stk_name = domain_df.loc[idx, 'display_name']
            kind = domain_df.loc[idx, 'kind_condensation']
            f_code = domain_df.loc[idx, 'code']
            time_span = self.get_single_trade_time_span(f_code=f_code)
            r_dict.append({
                "name": stk_name,
                "kind": kind,
                "time_span": time_span
            })

        return r_dict

    @staticmethod
    def get_futures_kind(stk_code):
        if '.' in stk_code:
            code_simple = stk_code.split('.')[0]
        else:
            code_simple = stk_code
        return NlReFilter.filter_letter_from_str(code_simple)

    @staticmethod
    def get_jq_futures_exchange_id(stk_code):
        """
        获取exchangeID
        CFFEX中金所、CZCE郑商所、DCE大商所、INE上能所、SHFE上期所
        :return:
        """
        post_fix = stk_code.split('.')[1]
        return {"CCFX": "CFFEX", "XDCE": "DCE", "XSGE": "SHFE", "XZCE": "CZCE", "XINE": "INE"}.get(post_fix, None)

    @staticmethod
    def convert_stk_code_to_ism_id(stk):

        return jq.get_security_info(stk).name

        # if '.' in str(stk):
        #     stk_id = str(stk).split('.')[0]
        # else:
        #     stk_id = stk
        #
        # # 大写转小写
        # return stk_id.lower()

    # @staticmethod
    # def convert_stk_code_to_ism_id_new(stk):
    #     if '.' in str(stk):
    #         stk_id = str(stk).split('.')[0]
    #     else:
    #         stk_id = stk
    #
    #     letter = NlReFilter.filter_letter_from_str(stk_id)
    #     if letter in ['SF', 'SM', 'AP', 'CJ', 'UR', 'SR', 'CF', 'TA', 'MA', 'RM', 'OI', 'FG', 'ZC', 'CY', 'SA', 'PF', 'IF', 'IH', 'IC', 'TF', 'T']:
    #         return stk_id
    #     else:
    #         # 大写转小写
    #         return stk_id.lower()


if __name__ == '__main__':
    jq.auth('13871922088', 'Ypw@522109')

    fd = FuturesData()
    r = fd.get_futures_trade_date()

    dump_p(r, save_location=root_path + '/', file_name='futures_trade_timespan')

    end = 0
