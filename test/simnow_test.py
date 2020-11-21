# encoding=utf-8

"""
仿真
"""
import time

from Server.futures.ctp.my_ctp_api.ctp_class_no_use import MyCtp
from Server.futures.futures_account_info.account_info import ctp_login_info_sim


from my_config.log import MyLog
ml = MyLog('ctp_sim')
logger = ml.logger

if __name__ == '__main__':
    mctp = MyCtp(ctp_login_info=ctp_login_info_sim)
    mctp.login()

    while True:
        if mctp.ctp_spi.login_success:
            # mctp.req_order_field_insert(
            #     instrument_id='m2009',
            #     price=2700,
            #     volume=1,
            #     offset='0',
            #     direction='b')
            # mctp.ctp_spi.login_success = False

            # 撤
            # mctp.req_order_action(mctp.ctp_spi.ccl.cmd_dict[list(mctp.ctp_spi.ccl.cmd_dict.keys())[0]].cmd_id)

            # 查
            # r = req_qry_investor_position('m2009')
            logger.debug('登录成功！')

        time.sleep(2)
        logger.debug(str(mctp.ctp_spi.ccl.cmd_dict))

        # msg = get_current_datetime_str() + ':一次循环完成'
        # logger.debug(get_current_datetime_str() + ':一次循环完成')