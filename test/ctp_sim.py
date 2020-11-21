# encoding=utf-8
import logging
import time
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

    # 打印挂单信息
    print(mctp.ctp_spi.ccl.print_order_info())

    # 撤单
    mctp.pack_order_action('1x-1119290736x1120205836-1', 'jm2101')

    while True:

        if mctp.ctp_spi.login_success:

            # 下单
            mctp.req_order_field_insert(
                instrument_id='jm2101',
                price=1440,
                volume=1,
                offset='1',
                direction='b')
            time.sleep(5)
            mctp.update_position()

            # 发送更新持仓命令
            mctp.req_investor_position_all()
            time.sleep(600)