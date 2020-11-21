# encoding=utf-8

AUTH_CODE = 'ZLJN90JFX7P2LBLR'
APP_ID = 'client_modeng_1.0.0'

#Addr
FRONT_ADDR_TRADE= "tcp://180.166.103.21:55205"
FRONT_ADDR_DATA= "tcp://180.166.103.21:55213"

#LoginInfo
BROKER_ID="4040"
USER_ID="8118018200"
PASSWORD="ypw313789"

ctp_login_info = {
    "auth_code": 'ZLJN90JFX7P2LBLR',
    "app_id": 'client_modeng_1.0.0',
    "front_addr_trade": "tcp://180.166.103.21:55205",
    "front_addr_data": "tcp://180.166.103.21:55213",
    "broker_id": "4040",
    "user_id": "8118018200",
    "password": "ypw313789"
}

ctp_login_info_sim = {
    "auth_code": '0000000000000000',
    "app_id": 'simnow_client_test',
    "front_addr_trade": "tcp://180.168.146.187:10100",
    "front_addr_data": "tcp://180.168.146.187:10110",
    "broker_id": "9999",
    "user_id": "176279",
    "password": "ypw@1989"
}

"""
 BrokerID统一为：9999
标准CTP：
    第一组：Trade Front：180.168.146.187:10100，Market Front：180.168.146.187:10110；【电信】
    第二组：Trade Front：180.168.146.187:10101，Market Front：180.168.146.187:10111；【电信】
    第三组：Trade Front： 218.202.237.33 :10102，Market Front：218.202.237.33 :10112；【移动】
7*24小时环境：
    第一组：Trade Front： 180.168.146.187:10130，Market Front：180.168.146.187:10131；【电信】

"""