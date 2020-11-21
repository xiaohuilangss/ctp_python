# encoding=utf-8
import logging
import jqdatasdk as jq

from ctp.my_ctp_api.ctp_class import MyCtp
from my_config.futures_account_info import ctp_login_info_sim
from sdk.log_print.log import MyLog

logger_eml = MyLog('ctp_sim_eml', file_level=logging.INFO).logger

if __name__ == '__main__':

    # 登陆聚宽账号
    jq.auth('13871922088', 'Ypw@522109')

    # 创建ctp
    mctp = MyCtp(ctp_login_info=ctp_login_info_sim)
    mctp.login()

    # 订阅期货m2101的实时数据
    mctp.mmc.sub_rt_data(['m2101'])

    # 获取实时数据
    while True:
        print(str(mctp.mmc.get_stk_rt_price('m2101')))