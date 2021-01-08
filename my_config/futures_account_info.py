# encoding=utf-8


ctp_login_info = {
    "auth_code": '0000000000000000',
    "app_id": 'simnow_client_test',
    "front_addr_trade": "tcp://180.168.146.187:10100",
    "front_addr_data": "tcp://180.168.146.187:10110",
    "broker_id": "9999",
    "user_id": "*****",
    "password": "****"
}

# TODO 此处需要用户在simnow注册账号，并将user_id 和 password 填上，才能使用！
ctp_login_info_sim = {
    "auth_code": '0000000000000000',
    "app_id": 'simnow_client_test',
    "front_addr_trade": "tcp://180.168.146.187:10100",
    "front_addr_data": "tcp://180.168.146.187:10110",
    "broker_id": "9999",
    "user_id": "*****",
    "password": "*****"
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