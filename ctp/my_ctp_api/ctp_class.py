# encoding=utf-8
import logging

import numpy as np

from data_source.futures_data import FuturesData
from my_config.futures_account_info import ctp_login_info, ctp_login_info_sim
from my_config.global_setting import root_path
from sdk.MyTimeOPT import get_current_datetime_str, get_current_date_str

import thostmduserapi as mdapi
import thosttraderapi as api
import time
import os
import copy
import json

from sdk.log_print.log import MyLog

ml = MyLog('ctp')
logger = ml.logger
logger_ctp_eml = MyLog('ctp_mdopt_eml', file_level=logging.INFO, console_level=logging.DEBUG).logger




class CmdContent:
    def __init__(self, instrument_id, price, volume, offset, direction):
        self.direction = direction
        self.offset = offset
        self.volume = volume
        self.price = price
        self.instrument_id = instrument_id


class OrderStatus:
    """
    {
                "order_status": None,
                "order_submit_status": None,
                "status_msg": None,
                "error_id": [],
                "error_msg": []
            }
    """

    def __init__(self,
                 order_status=-1,
                 order_submit_status=None,
                 status_msg=None,
                 error_id=None, error_msg=None, limit_price=None):

        self.limit_price = limit_price

        if isinstance(error_id, type(None)):
            self.error_id = []
        else:
            self.error_id = error_id

        if isinstance(error_msg, type(None)):
            self.error_msg = []
        else:
            self.error_msg = error_msg

        self.status_msg = status_msg
        self.order_submit_status = order_submit_status
        self.order_status = order_status


class CtpCmd:
    """
    cmd_now = {
            "created_time": get_current_datetime_str(),
            "order_status":{
                "order_status": None,
                "order_submit_status": None,
                "status_msg": None,
                "error_id": [],
                "error_msg": []
            },
            "deal_status":{},
            "cmd_id": cmd_id,
            "cmd_content": cmd_content,
        }

    """

    def __init__(self, cmd_id, cmd_content):
        self.cmd_content = cmd_content
        self.cmd_id = cmd_id
        self.deal_status = {}
        self.order_status = OrderStatus()
        self.created_time = get_current_datetime_str()

    def get_dict(self):
        """
        获取该对象的字典形式，便于序列化
        :return:
        """
        dict = copy.deepcopy(self.__dict__)
        dict['cmd_content'] = dict['cmd_content'].__dict__
        dict['order_status'] = dict['order_status'].__dict__
        return dict


class CmdId:
    def __init__(self, front_id, session_id, order_ref):
        self.order_ref = order_ref
        self.session_id = session_id
        self.front_id = front_id
        self.cmd_id = str(front_id) + 'x' + str(session_id) + 'x' + order_ref


class CTradeSpi(api.CThostFtdcTraderSpi):
    def __init__(self, t_api, ctp_login_info, opt=None):
        api.CThostFtdcTraderSpi.__init__(self)

        self.opt = opt
        """
        维护本次链接信息
        FrontID是CTP后台前置编号， SessionID是这次链接的编号，
        登录成功回报中也会返回这两个字段，这两个编号在此次连接中是不变的。
        """
        self.connect_status = {}

        # 维护此次连接相关命令
        self.ccl = CtpCmdList()

        self.ctp_login_info = ctp_login_info
        self.t_api = t_api

        # 登录成功标志位
        self.login_success = False

        # 保存登陆信息
        self.p_rsp_user_login = None

        self.position = []
        self.position_tmp = []

        self.position_update_flag = False

    def OnFrontConnected(self) -> "void":
        logger_ctp_eml.info('\n\n（一）前端连接成功！')

        auth_field = api.CThostFtdcReqAuthenticateField()
        auth_field.BrokerID = self.ctp_login_info['broker_id']
        auth_field.UserID = self.ctp_login_info['user_id']
        auth_field.AppID = self.ctp_login_info['app_id']
        auth_field.AuthCode = self.ctp_login_info['auth_code']

        self.t_api.ReqAuthenticate(auth_field, 0)
        logger_ctp_eml.info('\n（二）已发送认证请求！')

    def OnRspAuthenticate(
            self,
            pRspAuthenticateField: 'CThostFtdcRspAuthenticateField',
            pRspInfo: 'CThostFtdcRspInfoField',
            nRequestID: 'int',
            bIsLast: 'bool') -> "void":
        logger.debug("BrokerID=%s" % str(pRspAuthenticateField.BrokerID))
        logger.debug("UserID=%s" % str(pRspAuthenticateField.UserID))
        logger.debug("AppID=%s" % str(pRspAuthenticateField.AppID))
        logger.debug("AppType=%s" % str(pRspAuthenticateField.AppType))
        logger.debug("ErrorID=%s" % str(pRspInfo.ErrorID))
        logger.debug("ErrorMsg=%s" % str(pRspInfo.ErrorMsg))

        if not pRspInfo.ErrorID:
            login_field = api.CThostFtdcReqUserLoginField()
            login_field.BrokerID = self.ctp_login_info['broker_id']
            login_field.UserID = self.ctp_login_info['user_id']
            login_field.Password = self.ctp_login_info['password']
            login_field.UserProductInfo = "python dll"
            self.t_api.ReqUserLogin(login_field, 0)
            logger_ctp_eml.info("\n（三）已发送登录请求！")
        else:
            logger_ctp_eml.error("\n（三）认证请求失败，无法发送登陆请求！")

    def OnRspUserLogin(
            self,
            pRspUserLogin: 'CThostFtdcRspUserLoginField',
            pRspInfo: 'CThostFtdcRspInfoField',
            nRequestID: 'int',
            bIsLast: 'bool') -> "void":

        logger_ctp_eml.info("\n\n（三）收到登录回应！")
        logger_ctp_eml.debug("TradingDay=%s" % str(pRspUserLogin.TradingDay))
        logger_ctp_eml.debug("SessionID=%s" % str(pRspUserLogin.SessionID))
        logger_ctp_eml.debug("ErrorID=%s" % str(pRspInfo.ErrorID))
        logger_ctp_eml.debug("ErrorMsg=%s" % str(pRspInfo.ErrorMsg))

        # 将session id保存在连接信息中
        self.connect_status['session_id'] = str(pRspUserLogin.SessionID)
        self.connect_status['front_id'] = str(pRspUserLogin.FrontID)

        # 发送【查询投资者结算结果】请求
        if not pRspInfo.ErrorID:
            qry_info_field = api.CThostFtdcQrySettlementInfoField()
            qry_info_field.BrokerID = self.ctp_login_info['broker_id']
            qry_info_field.InvestorID = self.ctp_login_info['user_id']
            qry_info_field.TradingDay = pRspUserLogin.TradingDay
            self.t_api.ReqQrySettlementInfo(qry_info_field, 0)
            logger_ctp_eml.info("（四）成功发送【查询投资者结算结果】请求！")
        else:
            logger_ctp_eml.error("（四）发送【查询投资者结算结果】请求失败！")

    def OnRspQrySettlementInfo(
            self,
            pSettlementInfo: 'CThostFtdcSettlementInfoField',
            pRspInfo: 'CThostFtdcRspInfoField',
            nRequestID: 'int',
            bIsLast: 'bool') -> "void":
        """
        查询投资者结算结果
        为了让投资者了解当前的交易风险。
        终端程序要在第一次发送交易指令之前，
        查询投资者结算结果(ReqQrySettlementInfo)和确认投资者结算结果 (ReqSettlementInfoConfirm)，
        才能正常发送交易指令，包括报单、撤单、服务器预埋单等指令。

        :param pSettlementInfo:
        :param pRspInfo:
        :param nRequestID:
        :param bIsLast:
        :return:
        """

        logger_ctp_eml.info("（四）收到【查询投资者结算结果】回应！")
        if pSettlementInfo is not None:
            logger_ctp_eml.debug("content:%s" % str(pSettlementInfo.Content))
        else:
            logger_ctp_eml.warning("content null")

        p_settlement_info_confirm = api.CThostFtdcSettlementInfoConfirmField()
        p_settlement_info_confirm.BrokerID = self.ctp_login_info['broker_id']
        p_settlement_info_confirm.InvestorID = self.ctp_login_info['user_id']
        self.t_api.ReqSettlementInfoConfirm(p_settlement_info_confirm, 0)
        logger_ctp_eml.info("（五）成功发送【确认投资者结算结果】的请求!")

    def OnRspSettlementInfoConfirm(
            self,
            pSettlementInfoConfirm: 'CThostFtdcSettlementInfoConfirmField',
            pRspInfo: 'CThostFtdcRspInfoField',
            nRequestID: 'int', bIsLast: 'bool') -> "void":
        """
        投资者结算结果确认，在开始每日交易前都需要先确认上一日结算单，
        只需要确认一次
        :param pSettlementInfoConfirm:
        :param pRspInfo:
        :param nRequestID:
        :param bIsLast:
        :return:
        """

        logger_ctp_eml.info("（五）收到【确认投资者结算结果】请求的回应，整个登陆流程完成！")
        logger_ctp_eml.debug("ErrorID=%s" % str(pRspInfo.ErrorID))
        logger_ctp_eml.debug("ErrorMsg=%s" % str(pRspInfo.ErrorMsg))

        # 设置标志位，指示登录成功
        if pRspInfo.ErrorID == 0:
            self.login_success = True

    def cmd_exist(self, cmd_id):
        # 登记命令状态
        if not cmd_id in self.ccl.cmd_dict.keys():
            logger_ctp_eml.error('收到命令【%s】回应，但是命令列表中未发现相应命令！无法更新该命令状态！\n当前命令列表内容：%s' % (cmd_id, str(self.ccl.cmd_dict)))
            return False
        else:
            return True

    def OnRtnTrade(self, pTrade: 'CThostFtdcTradeField') -> "void":
        try:
            logger_ctp_eml.info('收到成交回报！')

            # 获取cmd_id
            cmd_id = self.ccl.gen_cmd_id(front_id=self.connect_status['front_id'],
                                         session_id=self.connect_status['session_id'],
                                         order_ref=pTrade.OrderRef)

            logger_ctp_eml.info('\ncmd_id:%s\np:%s\nvolume:%s\noffset:%s\ndirection:%s\n' % (
            str(cmd_id), str(pTrade.Price), str(pTrade.Volume), str(pTrade.OffsetFlag), str(pTrade.Direction)))

            self.position_update_flag = True

        except Exception as e_:
            logger_ctp_eml.info('收到成交回报，但解析反馈结果时出错，原因：\n%s' % str(e_))

    def OnRtnOrder(self, pOrder: 'CThostFtdcOrderField') -> "void":
        """
        下单正常时，调用此函数
        只有OnRtnOrder函数（如有成交则会单独回调OnRtnTrade函数），回调参数类型为CThostFtdcOrderField。
        这个参数同样有很多字段，有的字段组合是用来区分该笔回报对应的哪笔原始报单，
        有的用来反应报单状态等等。

        OrderStatus             报单状态
        OrderSubmitStatus       报单提交状态
        StatusMsg               状态信息

        :param pOrder:
        :return:
        """
        logger_ctp_eml.info('收到下单回报：\n状态：%s  \nmsg：%s  \np:%s\n' % (
            str(pOrder.OrderStatus), str(pOrder.StatusMsg), str(pOrder.LimitPrice)))

        # 获取cmd_id
        cmd_id = self.ccl.gen_cmd_id(front_id=pOrder.FrontID, session_id=pOrder.SessionID, order_ref=pOrder.OrderRef)

        if self.cmd_exist(cmd_id):
            self.ccl.cmd_dict[cmd_id].order_status.order_status = pOrder.OrderStatus
            self.ccl.cmd_dict[cmd_id].order_status.status_msg = pOrder.StatusMsg
            self.ccl.cmd_dict[cmd_id].order_status.limit_price = pOrder.LimitPrice
            logger_ctp_eml.info('已完成ccl中的单子状态更新！')

        # ccl本地序列化保存
        try:
            self.ccl.dump_cmd_dict_to_json_file()
            logger.debug('ccl 本地序列化成功！')
        except Exception as e_:
            logger_ctp_eml.exception('ccl 本地序列化出错！原因：\n%s' % str(e_))

    def OnRspOrderInsert(
            self,
            pInputOrder: 'CThostFtdcInputOrderField',
            pRspInfo: 'CThostFtdcRspInfoField',
            nRequestID: 'int',
            bIsLast: 'bool') -> "void":
        """
        报单录入请求响应，当执行ReqOrderInsert后有字段填写不对之类的CTP报错则通过此接口返回
        :param pInputOrder:
        :param pRspInfo:
        :param nRequestID:
        :param bIsLast:
        :return:
        """
        logger_ctp_eml.error("进入【OnRspOrderInsert】函数:进入此函数意味着下发命令出错！\nErrorID:%s\nErrorMSG:%s\nOrderRef:%s" % (
            str(pRspInfo.ErrorID), str(pRspInfo.ErrorMsg), str(pInputOrder.OrderRef)))

        # 获取cmd_id
        cmd_id = self.ccl.gen_cmd_id(
            front_id=self.connect_status['front_id'],
            session_id=self.connect_status['session_id'],
            order_ref=pInputOrder.OrderRef)

        if self.cmd_exist(cmd_id):
            self.ccl.cmd_dict[cmd_id].order_status.error_id.append(pRspInfo.ErrorID)
            self.ccl.cmd_dict[cmd_id].order_status.error_msg.append(pRspInfo.ErrorMsg)

    def OnRspOrderAction(self, pInputOrderAction: 'CThostFtdcInputOrderActionField', pRspInfo: 'CThostFtdcRspInfoField', nRequestID: 'int', bIsLast: 'bool'):
        logger_ctp_eml.debug('撤函数收到回应！\nErrorId:%s\nErrorMsg:%s' % (str(pRspInfo.ErrorID), str(pRspInfo.ErrorMsg)))

    def OnRspQryInvestorPosition(self, pInvestorPosition: 'CThostFtdcInvestorPositionField',
                                 pRspInfo: 'CThostFtdcRspInfoField', nRequestID: 'int', bIsLast: 'bool') -> "void":
        """
        :param pInvestorPosition:
        :param pRspInfo:
        :param nRequestID:
        :param bIsLast:
        :return:
        """

        """
        主要字段解释：

            InstrumentID  合约ID    
            BrokerID
            InvestorID

            PosiDirection 多空方向 2:多头持仓 3：空头持仓
            HedgeFlag 投机套保标志 多数默认为“1”， 即投机仓
            PositionDate 日期


            YdPosition
            Position
            LongFrozen  多头冻结数量
            ShortFrozen 空头冻结数量
            LongFrozenAmount
            ShortFrozenAmount
            OpenVolume 开仓量
            CloseVolume 平仓量
            OpenAmount
            CloseAmount
            PositionCost持仓成本
            PreMargin
            UseMargin
            FrozenMargin
            FrozenCash
            FrozenCommission
            CashIn
            Commission
            CloseProfit 平仓盈亏
            PositionProfit 持仓盈亏
            PreSettlementPrice
            SettlementPrice
            TradingDay
            SettlementID
            OpenCost
            ExchangeMargin
            CombPosition
            CombLongFrozen
            CombShortFrozen
            CloseProfitByDate
            CloseProfitByTrade
            TodayPosition
            MarginRateByMoney
            MarginRateByVolume
            StrikeFrozen
            StrikeFrozenAmount
            AbandonFrozen
            ExchangeID
            YdStrikeFrozen
            InvestUnitID
            PositionCostOffset
        """
        if isinstance(pInvestorPosition, type(None)):
            logger_ctp_eml.debug('cc更新得到的信息为空，可能是kc！')
            return
        else:
            logger_ctp_eml.debug('接受到cc更新反馈！')
        try:
            self.position_tmp.append({
                "InstrumentID": pInvestorPosition.InstrumentID,
                "BrokerID": pInvestorPosition.BrokerID,
                "InvestorID": pInvestorPosition.InvestorID,
                "PosiDirection": pInvestorPosition.PosiDirection,
                "HedgeFlag": pInvestorPosition.HedgeFlag,
                "PositionDate": pInvestorPosition.PositionDate,
                "YdPosition": pInvestorPosition.YdPosition,
                "Position": pInvestorPosition.Position,
                "LongFrozen": pInvestorPosition.LongFrozen,
                "ShortFrozen": pInvestorPosition.ShortFrozen,
                "OpenVolume": pInvestorPosition.OpenVolume,
                "CloseVolume": pInvestorPosition.CloseVolume,
                "CloseProfit": pInvestorPosition.CloseProfit,
                "PositionProfit": pInvestorPosition.PositionProfit,
                "ExchangeID": pInvestorPosition.ExchangeID,
                "SettlementPrice": pInvestorPosition.SettlementPrice
            })
            if bIsLast:
                self.position = self.position_tmp
                self.position_tmp = []
                logger_ctp_eml.info(
                    '收到cc查询已完成！更新后的非空cc情况：\n%s' % str(list(filter(lambda x: x['Position'] > 0, self.position))).replace(
                        ',', '\n').replace('{', '\n').replace('}', '\n'))
        except Exception as e:
            logger_ctp_eml.exception('cc信息更新失败！具体原因：\n%s' % str(e))

    def OnErrRtnOrderAction(self, pOrderAction: 'CThostFtdcOrderActionField', pRspInfo: 'CThostFtdcRspInfoField'):
        logger_ctp_eml.error('撤单失败！\nErrorId:%s\nErrorMsg:%s' % (str(pRspInfo.ErrorID), str(pRspInfo.ErrorMsg)))


class CtpCmdList:
    """
    这个类用来维护命令列表，包括但不限于：
    1、维护命令信息
    2、更新命令状态（下单成功？成交量？）
    3、出错提示
    """
    """
            本地维护下发的命令，字典列表形式

            FrontID        //前置编号
            SessionID     //会话编号
            OrderRef       //报单引用
            ExchangeID    //交易所代码
            TraderID      //交易所交易员代码
            OrderLocalID  //本地报单编号
            OrderSysID    //报单编号

            说明：在CTP中，每笔报单都有 3 组唯一序列号，保证其与其他报单是不重复的。

            1) FrontID + SessionID + OrderRef
            FrontID是CTP后台前置编号， SessionID是这次链接的编号，
            登录成功回报中也会返回这两个字段，这两个编号在此次连接中是不变的。

            OrderRef返回的是客户报单请求时填写的对应字段。
            例如如果客户请求时在CThostFtdcInputOrderField的OrderRef中填100，
            那么回报中CThostFtdcOrderField中OrderRef也为100。
            但是请求时OrderRef不是必填字段，如果没填，CTP会自动递增地为该字段赋值。
            （但要注意如果是CTP自动生成的，该字段是右对齐的，后面使用该字段时都需要保持一致）

            所以每次报单时，我们可以用FrontID + SessionID + OrderRef组成一个key在本地标识存入唯一的一笔报单，
            当有报单回报返回时，就可以根据回报中的这三个字段找出原始的请求报单，
            再用回报中的状态来更新原始请求报单的当前状态。
            客户也可以用这三组序号填入到请求撤单对应的字段里去随时撤单。

            2）ExchangeID + OrderSysID
            OrderSysID是报单报入到交易所时交易所给编的唯一编号，
            所以这个字段加上ExchangeID也可以用来确定唯一一笔报单。
            需要特别注意的是，在上图中，该笔报单请求首次到达CTP，
            风控通过后返回的第1个OnRtnOrder回报，此时因为还没有报入到交易所，
            所以回报中OrderSysID为空。这一组字段也可以用于撤单时指定唯一一笔订单。

            按照前面讲的，有了第一组FrontID + SessionID + OrderRef就应该可以全场确定唯一一笔订单了，
            为什么还要有后面两组呢？这里有一个坑。当客户的报单有成交时，CTP会推送成交回报，
            就是上图中和第3个OnRtnOder一起来的OnRtnTrade回报。
            成交回报中没有FrontID 和SessionID字段，只有OrderRef字段……

            所以建议有两种方案维护自己的订单表：

            01
            报单时用FrontID + SessionID + OrderRef维护本地报单，当第2个OnRtnOder回来后，
            找到原始报单，将OrderSysID填入到本地报单中，后面都用ExchangeID + OrderSysID维护订单

            02
            本地维护OrderRef字段，当前交易日内不管多少链接都一直单调递增，
            这样就可以不管FrontID 和 SessionID ，每次根据OrderRef就可以确定唯一报单。
            但这对多策略多链接交易开发可能存在问题，因为涉及到多个API链接间OrderRef字段的互相同步。
            """

    def __init__(self):

        # 维护一个命令列表
        self.cmd_dict = {}
        self.order_ref_index = 0

        # 本地序列化文件路径
        self.cmd_save_dir = root_path + '/source/ctp_cmd_json/'

    def convert_obj_to_json(self):
        if len(self.cmd_dict) == 0:
            return self.cmd_dict

        cmd_dict_copy = copy.deepcopy(self.cmd_dict)

        # 对字典内的对象转为字典类型
        for k in cmd_dict_copy.keys():
            cmd_dict_copy[k] = cmd_dict_copy[k].get_dict()

        return cmd_dict_copy

    def get_json_file_name(self):
        """
        获取本地文件序列化路径
        :return:
        """
        if not os.path.exists(self.cmd_save_dir):
            os.mkdir(self.cmd_save_dir)

        # 打开/创建本地文件
        return self.cmd_save_dir + 'ctp_cmd_' + get_current_date_str() + '.json'

    def dump_cmd_dict_to_json_file(self):
        """
        将cmd_dict序列化为本地json对象
        :return:
        """
        try:
            # 打开/创建本地文件
            file_url = self.get_json_file_name()
            f = open(file_url, 'w')

            # 获取cmd_dict 变量的字典类型
            cmd_dict = self.convert_obj_to_json()

            json.dump(cmd_dict, f)
            f.close()
            logger_ctp_eml.info('ccl信息序列化为本地json文件成功！具体内容为%s' % str(cmd_dict))
        except Exception as e_:
            logger_ctp_eml.exception('cmd_dict 序列化为本地json文件时出错！原因：\n%s' % str(e_))

    @staticmethod
    def convert_dict_to_cmd_obj(cmd_dict):
        cc = CtpCmd(cmd_content=cmd_dict['cmd_content'], cmd_id=cmd_dict['cmd_id'])

        cc.created_time = cmd_dict['created_time']
        cc.deal_status = cmd_dict['deal_status']
        cc.order_status = cmd_dict['order_status']

        cc.cmd_content = CmdContent(
            instrument_id=cc.cmd_content['instrument_id'],
            price=cc.cmd_content['price'],
            volume=cc.cmd_content['volume'],
            offset=cc.cmd_content['offset'],
            direction=cc.cmd_content['direction'])

        order_status_dict = cmd_dict['order_status']
        cc.order_status = OrderStatus(
            order_status=order_status_dict['order_status'],
            order_submit_status=order_status_dict['order_submit_status'],
            status_msg=order_status_dict['status_msg'],
            error_id=order_status_dict['error_id'],
            error_msg=order_status_dict['error_msg'],
            limit_price=order_status_dict['limit_price'])

        return cc

    def print_order_info(self):
        str_info_str = ''
        for k, v in self.cmd_dict.items():
            str_info_str = str_info_str + '%s的ccw信息为：\ncmd_content:%s\ncmd_id:%s\ncreate_time:%s\ndeal_status:%s\norder_status:%s\n\n' % (
                str(k), str(v.cmd_content.__dict__), v.cmd_id, v.created_time, str(v.deal_status), str(v.order_status.__dict__))

        return str_info_str

    def update_cmd_dict_by_local_json_file(self):
        try:

            f_url = self.get_json_file_name()
            if not os.path.exists(f_url):
                logger_ctp_eml.warning('本地未找到文件【%s】，请确认当前是当天初启动且未有操作！' % f_url)
                self.cmd_dict = {}
                return

            f = open(f_url, 'r')

            cmd_dict = json.load(f)

            for k in cmd_dict.keys():
                cmd_dict[k] = self.convert_dict_to_cmd_obj(cmd_dict[k])

            self.cmd_dict = cmd_dict
            logger_ctp_eml.info('cmd_dict反序列化成功！得到内容为：%s' % str(cmd_dict))

        except Exception as e_:
            logger_ctp_eml.exception('cmd_dict反序列化出错！原因：\n %s' % str(e_))

    def add_cmd_to_dict(self,
                        session_id,
                        front_id,
                        order_ref,
                        instrument_id,
                        price,
                        volume,
                        offset,
                        direction):
        """
        将命令添加到命令字典
        :param direction:
        :param offset:
        :param volume:
        :param price:
        :param instrument_id:
        :param order_ref:
        :param front_id:
        :param session_id:
        :param cmd:
        :return:
        """
        try:
            cmd_content = CmdContent(
                instrument_id=instrument_id,
                price=price,
                volume=volume,
                offset=offset,
                direction=direction)

            cmd_id_obj = CmdId(
                session_id=session_id,
                front_id=front_id,
                order_ref=order_ref)

            cmd = self.gen_new_cmd(cmd_id_obj.cmd_id, cmd_content)
            self.cmd_dict[cmd_id_obj.cmd_id] = cmd
            logger_ctp_eml.debug('登记命令成功，登记后命令内容为：\n%s' % str(self.cmd_dict[cmd_id_obj.cmd_id].__dict__))

        except Exception as e_:
            logger_ctp_eml.exception('登记命令失败！原因：\n%s' % str(e_))

    def gen_order_ref(self):
        self.order_ref_index = self.order_ref_index + 1
        return get_current_datetime_str().replace(' ', '').replace('-', '').replace(':', '')[4:] + '-' + str(
            self.order_ref_index)

    def gen_cmd_id(self, session_id, front_id, order_ref=None):
        """
        创建命令id
        :param order_ref:
        :param session_id:
        :param front_id:
        :return:
        """

        # 增加此判断是为了可以复用这个函数
        if isinstance(order_ref, type(None)):
            order_ref = self.gen_order_ref()

        return str(front_id) + 'x' + str(session_id) + 'x' + order_ref

    @staticmethod
    def gen_new_cmd(cmd_id, cmd_content):
        return CtpCmd(cmd_id=cmd_id, cmd_content=cmd_content)

    def get_cmd_bs_status(self):
        """
        查找是否有未成的bs
        :return:
        """
        try:
            r_cpl = {'b': False, 's': False}
            if len(self.cmd_dict) == 0:
                return r_cpl

            # 筛选出未成单（存在非0和非5的单子）
            order_list = list(self.cmd_dict.values())
            order_no_cpl = list(
                filter(lambda x: (int(x.order_status.order_status) != 0) & (int(x.order_status.order_status) != 5),
                       order_list))

            opt_no_cpl = [x.cmd_content.direction for x in order_no_cpl]

            if (0 in opt_no_cpl) | ('b' in opt_no_cpl):
                r_cpl['b'] = True
                logger.debug('有b未成单！')
            if (1 in opt_no_cpl) | ('s' in opt_no_cpl):
                r_cpl['s'] = True
                logger.debug('有s未成单！')
            return r_cpl
        except Exception as e_:
            logger_ctp_eml.exception('异常，不许发任何命令，异s常原因：\n %s' % str(e_))
            return {'b': True, 's': True}


class MyCtp:
    """
    最终使用的主类
    """

    def __init__(self, ctp_login_info, opt=None):
        self.opt = opt
        self.ctp_login_info = ctp_login_info

        self.mmc = MyMdCpt(ctp_login_info)

        # ctp 命令及响应类的对象
        self.ctp_api = api.CThostFtdcTraderApi_CreateFtdcTraderApi()
        self.ctp_spi = CTradeSpi(self.ctp_api, self.ctp_login_info)

    def logout(self):
        logger_ctp_eml.info('开始执行释放连接操作...')
        r = self.ctp_api.Release()
        # self.mmc.logout()
        logger_ctp_eml.info('释放连接操作完成，返回值%s' % str(r))
        self.ctp_spi.login_success = False

    def login(self):
        """
        登陆ctp
        :return:
        """
        self.ctp_api = api.CThostFtdcTraderApi_CreateFtdcTraderApi()
        self.ctp_spi = CTradeSpi(self.ctp_api, self.ctp_login_info, opt=self.opt)
        self.ctp_api.RegisterFront(self.ctp_login_info['front_addr_trade'])
        self.ctp_api.RegisterSpi(self.ctp_spi)
        self.ctp_api.SubscribePrivateTopic(api.THOST_TERT_QUICK)
        self.ctp_api.SubscribePublicTopic(api.THOST_TERT_QUICK)
        self.ctp_api.Init()

        time.sleep(10)
        self.mmc.login()

        # 加载本地ccl信息
        self.ctp_spi.ccl.update_cmd_dict_by_local_json_file()

        # time.sleep(10)
        # self.ctp_api.Join()

    def req_order_field_insert(self, instrument_id, price, volume, offset, direction, any_price=False,
                               debug=False):
        """
        下单
        :param trade_api:
        :param exchange_id:     交易所代码(CFFEX中金所、CZCE郑商所、DCE大商所、INE上能所、SHFE上期所，生产可不填？)
        :param instrument_id:   品种代码（郑商所大写+三位数，其余小写+四位数） （例如"RM005"）

        :param price:           是报单价格，只有OrderPriceType是限价单的时候需要填写，
                                填写的时候注意价格要是最小报价单位（查询合约可得）的整数倍，否则会被拒单。（例如 3200）

        :param volume:          （例如 1）
        :param offset:          组合开平标志
                                THOST_FTDC_OF_Open->开仓，
                                THOST_FTDC_OF_Close->平仓/平昨，
                                THOST_FTDC_OF_CloseToday->平今。
                                除了上期所/能源中心外，不区分平今平昨，平仓统一使用THOST_FTDC_OF_Close)
                                OFFSET="0"  #开仓0
                                #OFFSET="1" #平仓1

        :param direction:       买卖方向 封装为字符串"b" "s"
                                api.THOST_FTDC_D_Sell
                                api.THOST_FTDC_D_Buy
        :return:
        """
        try:
            logger_ctp_eml.info("开始报单！")
            order_ref = self.ctp_spi.ccl.gen_order_ref()

            # 在平的情况下，判断平今与平左
            if offset == '1':

                # 生成order_ref
                stk_cc_info = self.get_sig_stk_cc_info(ism_id=instrument_id,
                                                       posi_direction={'b': '3', 's': '2'}.get(direction))
                exchange_id = stk_cc_info['ExchangeID']

                try:
                    if isinstance(stk_cc_info, type(None)):
                        logger_ctp_eml.error('在对%s进行平操作时，未查询到其持仓信息，下发命令函数返回！' % instrument_id)
                        return None
                    else:
                        if (exchange_id in ['SHFE', 'INE']) & (stk_cc_info['PositionDate'] == '1'):
                            logger_ctp_eml.info('检测到上期、上能单，并且为今单，单独使用平今参数！\nism_id:%s\nExchangeID：%s' % (
                            instrument_id, exchange_id))
                            offset = api.THOST_FTDC_OF_CloseToday
                except Exception as e:
                    logger_ctp_eml.info(
                        '检测到上期、上能单，并且为今单，单独使用平今参数时出错！原因：\n%s\n本stk cc信息：%s' % (str(e), str(stk_cc_info)))

            order_field = api.CThostFtdcInputOrderField()
            order_field.BrokerID = self.ctp_login_info['broker_id']
            # order_field.ExchangeID = exchange_id
            order_field.InstrumentID = instrument_id
            order_field.UserID = self.ctp_login_info['user_id']
            order_field.InvestorID = self.ctp_login_info['user_id']
            order_field.Direction = {'b': api.THOST_FTDC_D_Buy, 's': api.THOST_FTDC_D_Sell}.get(direction)
            order_field.LimitPrice = price
            order_field.VolumeTotalOriginal = volume

            # 报单价格类型(THOST_FTDC_OPT_LimitPrice（限价）和THOST_FTDC_OPT_AnyPrice（市价）)
            if any_price:
                order_field.OrderPriceType = api.THOST_FTDC_OPT_AnyPrice
            else:
                order_field.OrderPriceType = api.THOST_FTDC_OPT_LimitPrice

            # 触发条件,一般为立即
            order_field.ContingentCondition = api.THOST_FTDC_CC_Immediately

            """
            TimeCondition是枚举类型，目前只有THOST_FTDC_TC_GFD和THOST_FTDC_TC_IOC这两种类型有用。
            GFD是指当日有效，报单会挂在交易所直到成交或收盘自动撤销。
            IOC是立即完成否则撤销，和VolumeCondition、MinVolume 字段配合用于设置FAK或FOK。
            """
            order_field.TimeCondition = api.THOST_FTDC_TC_GFD  # 有效期类型
            order_field.VolumeCondition = api.THOST_FTDC_VC_AV
            order_field.CombHedgeFlag = "1"  # 组合投机套保标志
            order_field.CombOffsetFlag = offset
            order_field.GTDDate = ""
            order_field.OrderRef = order_ref
            order_field.orderfieldRef = '1'
            order_field.MinVolume = 0
            order_field.ForceCloseReason = api.THOST_FTDC_FCC_NotForceClose  # 强平原因
            order_field.IsAutoSuspend = 0

            # 发送命令
            r = self.ctp_api.ReqOrderInsert(order_field, 0)
            logger_ctp_eml.info('ctp下发命令完成，下发函数返回值：%s' % str(r))

            # 登记命令
            # 登记命令（先登记再发送，为了避免ccl本地序列化时写文件冲突！）
            self.ctp_spi.ccl.add_cmd_to_dict(
                session_id=self.ctp_spi.connect_status['session_id'],
                front_id=self.ctp_spi.connect_status['front_id'],
                order_ref=order_ref,
                instrument_id=instrument_id,
                price=price,
                volume=volume,
                offset=offset,
                direction=direction)

            # 更新本地ccl的json文件
            self.ctp_spi.ccl.dump_cmd_dict_to_json_file()

            logger.info("报单结束！")
            cmd_id = self.ctp_spi.ccl.gen_cmd_id(
                session_id=self.ctp_spi.connect_status['session_id'],
                front_id=self.ctp_spi.connect_status['front_id'],
                order_ref=order_ref)

            logger_ctp_eml.info("报单结束！cmd_id为：%s" % str(cmd_id))
            logger_ctp_eml.info("更新后的命令列表内容：%s" % str(self.ctp_spi.ccl.cmd_dict))
            return cmd_id
        except Exception as e:
            logger_ctp_eml.exception('ctp 命令下发出错！原因：\n%s' % str(e))
            return None

    def req_order_action(self, order_ref):

        order_field = api.CThostFtdcInputOrderField()
        order_field.BrokerID = self.ctp_login_info['broker_id']
        order_field.UserID = self.ctp_login_info['user_id']
        order_field.InvestorID = self.ctp_login_info['user_id']
        order_field.OrderRef = order_ref

        self.ctp_api.ReqOrderAction(order_field, 0)

    def req_qry_investor_position(self, instrument_id):
        """
        查看特定stk的cc
        :param instrument_id:
        :return:
        """
        ipf = api.CThostFtdcQryInvestorPositionField()
        ipf.BrokerID = self.ctp_login_info['broker_id']
        ipf.InvestorID = self.ctp_login_info['user_id']
        ipf.InstrumentID = instrument_id
        # ipf.ExchangeID =
        ipf.InvestUnitID = self.ctp_login_info['user_id']
        self.ctp_api.ReqQryInvestorPosition(ipf, 0)

    def req_investor_position_all(self):
        """
        查看全部cc
        :return:
        """
        logger_ctp_eml.debug('开始发送cc更新命令！')
        pf = api.CThostFtdcQryInvestorPositionField()
        return self.ctp_api.ReqQryInvestorPosition(pf, 0)

    def get_sig_stk_cc_volume(self, stk):
        """
        获取单个stk的cc
        :param stk:
        :return:
        """
        if len(self.ctp_spi.position) == 0:
            return 0
        elif FuturesData.convert_stk_code_to_ism_id(stk) not in [x['InstrumentID'] for x in self.ctp_spi.position]:
            return 0
        else:
            ism_id = FuturesData.convert_stk_code_to_ism_id(stk)
            ism_id_cc_list = list(filter(lambda x: x['InstrumentID'] == ism_id, self.ctp_spi.position))
            return np.sum([x['Position'] for x in ism_id_cc_list])

    def get_sig_stk_cc_info(self, ism_id, posi_direction):
        """
        根据多空方向获取指定stk的持仓
        :param posi_direction: ‘2’：多 ‘3’：空
        :param ism_id:
        :return:
        """
        info_list = list(filter(lambda x: (x['InstrumentID'] == ism_id) & (x['PosiDirection'] == posi_direction),
                                self.ctp_spi.position))
        if len(info_list) == 0:
            return None
        if len(info_list) != 1:
            logger_ctp_eml.error('%s多空方向为：%s，在持仓信息中查到的条数超过2条，可能属于异常情况！系统依然返回第一条数据！' % (ism_id, posi_direction))
            return info_list[0]
        else:
            return info_list[0]

    def pack_order_action(self, cmd_id, instrument_id):
        """
        cmd_id: str(front_id) + 'x' + str(session_id) + 'x' + order_ref
        pParkedOrderAction: 'CThostFtdcParkedOrderActionField', nRequestID: 'int'

        BrokerID
        InvestorID
        OrderActionRef
        OrderRef
        RequestID
        FrontID
        SessionID
        ExchangeID
        OrderSysID
        ActionFlag
        LimitPrice
        VolumeChange
        UserID
        :param cmd_id:
        :return:
        """
        ioa = api.CThostFtdcInputOrderActionField()
        ioa.BrokerID = self.ctp_login_info['broker_id']
        ioa.InvestorID = self.ctp_login_info['user_id']
        ioa.UserID = self.ctp_login_info['user_id']

        cmd_id_list = cmd_id.split('x')

        ioa.FrontID = int(cmd_id_list[0])
        ioa.SessionID = int(cmd_id_list[1])
        ioa.OrderRef = cmd_id_list[2]

        ioa.ActionFlag = api.THOST_FTDC_AF_Delete
        ioa.InstrumentID = instrument_id

        return self.ctp_api.ReqOrderAction(ioa, 0)

    def update_position(self):
        """
        此函数应当定频运行，以便保持cc信息及时更新
        :return:
        """
        if self.ctp_spi.position_update_flag:
            self.req_investor_position_all()
            self.ctp_spi.position_update_flag = False
            time.sleep(3)
            logger_ctp_eml.info('检测到成交回报将持仓更新标志位置True，ctp更新持仓并重置标志位！')
            not_null_cc = list(filter(lambda x: x['Position'] > 0, self.ctp_spi.position))
            if len(not_null_cc) > 0:
                logger_ctp_eml.info(
                    '当前非空仓位有！\n%s\n' % str(not_null_cc).replace(',', '\n').replace('{', '\n').replace('}', '\n'))
            else:
                logger_ctp_eml.info('当前仓位为空！')

            # 打印ccl信息
            logger_ctp_eml.info("ccl信息：%s" % str(self.ctp_spi.ccl.cmd_dict))


class CFtdcMdSpi(mdapi.CThostFtdcMdSpi):

    def __init__(self, tapi, ctp_login_info):
        mdapi.CThostFtdcMdSpi.__init__(self)
        self.ctp_login_info = ctp_login_info
        self.tapi = tapi
        self.sub_map = {}

    def OnFrontConnected(self) -> "void":
        logger_ctp_eml.debug("OnFrontConnected")
        try:
            loginfield = mdapi.CThostFtdcReqUserLoginField()
            loginfield.BrokerID = self.ctp_login_info['broker_id']
            loginfield.UserID = self.ctp_login_info['user_id']
            loginfield.Password = self.ctp_login_info['password']
            # loginfield.UserProductInfo = "python dll"
            self.tapi.ReqUserLogin(loginfield, 0)
        except Exception as e:
            logger_ctp_eml.exception('登录front出错！具体：%s' % str(e))

    def OnRspUserLogin(self, pRspUserLogin: 'CThostFtdcRspUserLoginField', pRspInfo: 'CThostFtdcRspInfoField',
                       nRequestID: 'int', bIsLast: 'bool') -> "void":
        logger_ctp_eml.debug(
            f"OnRspUserLogin, SessionID={pRspUserLogin.SessionID},ErrorID={pRspInfo.ErrorID},ErrorMsg={pRspInfo.ErrorMsg}")

    def OnRtnDepthMarketData(self, pDepthMarketData: 'CThostFtdcDepthMarketDataField') -> "void":
        # logger_ctp_eml.debug("OnRtnDepthMarketData")
        try:
            # mdlist = ([pDepthMarketData.TradingDay,
            #            pDepthMarketData.InstrumentID,
            #            pDepthMarketData.LastPrice,
            #            pDepthMarketData.PreSettlementPrice,
            #            pDepthMarketData.PreClosePrice,
            #            pDepthMarketData.PreOpenInterest,
            #            pDepthMarketData.OpenPrice,
            #            pDepthMarketData.HighestPrice,
            #            pDepthMarketData.LowestPrice,
            #            pDepthMarketData.Volume,
            #            pDepthMarketData.Turnover,
            #            pDepthMarketData.OpenInterest,
            #            pDepthMarketData.ClosePrice,
            #            pDepthMarketData.SettlementPrice,
            #            pDepthMarketData.UpperLimitPrice,
            #            pDepthMarketData.LowerLimitPrice,
            #            pDepthMarketData.PreDelta,
            #            pDepthMarketData.CurrDelta,
            #            pDepthMarketData.UpdateTime,
            #            pDepthMarketData.UpdateMillisec,
            #            pDepthMarketData.BidPrice1,
            #            pDepthMarketData.BidVolume1,
            #            pDepthMarketData.AskPrice1,
            #            pDepthMarketData.AskVolume1,
            #            pDepthMarketData.AveragePrice,
            #            pDepthMarketData.ActionDay])

            self.sub_map[pDepthMarketData.InstrumentID] = {
                'last_price': pDepthMarketData.LastPrice,
                'time': time.time()
            }
            # logger_ctp_eml.debug('%s：更新数据%s' % (str(pDepthMarketData.InstrumentID), str(pDepthMarketData.LastPrice)))

        except Exception as e:
            logger_ctp_eml.exception('获取rt futures数据失败！具体原因：\n%s' % str(e))

    def OnRspSubMarketData(self, pSpecificInstrument: 'CThostFtdcSpecificInstrumentField',
                           pRspInfo: 'CThostFtdcRspInfoField', nRequestID: 'int', bIsLast: 'bool') -> "void":
        logger_ctp_eml.debug("OnRspSubMarketData")
        logger_ctp_eml.debug("InstrumentID=%s" % pSpecificInstrument.InstrumentID)
        logger_ctp_eml.debug("ErrorID=%s" % pRspInfo.ErrorID)
        logger_ctp_eml.debug("ErrorMsg=%s" % pRspInfo.ErrorMsg)


class MyMdCpt:
    def __init__(self, login_ctp_info):
        self.login_ctp_info = login_ctp_info
        self.md_user_api = mdapi.CThostFtdcMdApi_CreateFtdcMdApi()
        self.md_user_spi = CFtdcMdSpi(self.md_user_api, ctp_login_info=ctp_login_info)
        self.login_success = False

    def sub_rt_data(self, sub_id_list):
        kind_list = [id.encode('utf-8') for id in sub_id_list]
        ret = self.md_user_spi.tapi.SubscribeMarketData(kind_list, len(sub_id_list))
        logger_ctp_eml.debug('已下发数据订阅命令！订阅pz：%s\n返回结果为：%s' % (str(kind_list), str(ret)))

    def login(self):
        if not self.login_success:
            self.md_user_api.RegisterFront(ctp_login_info['front_addr_data'])
            self.md_user_api.RegisterSpi(self.md_user_spi)
            self.md_user_api.Init()
            logger_ctp_eml.info('数据ctp初始化完成！')
            self.login_success = True
        else:
            logger_ctp_eml.info('数据ctp已登录，无需初始化！')

    def logout(self):
        """
        不好用
        :return:
        """
        try:
            self.md_user_api.release()
            logger_ctp_eml.info('数据ctp完成退出！')
        except Exception as e:
            logger_ctp_eml.exception('数据ctp退出失败！原因：\n%s' % str(e))

    def get_stk_rt_price(self, ism_id):
        if ism_id in self.md_user_spi.sub_map.keys():
            d_dict = self.md_user_spi.sub_map[ism_id]
            time_go = time.time() - d_dict['time']
            if time_go > 5:
                logger_ctp_eml.warning('%s:实时数据延迟警告，已滞后%0.1f秒!' % (ism_id, time_go))
            return d_dict['last_price']
        else:
            logger_ctp_eml.debug('%s:未获取实时数据，当前sub_map为：\n%s' % (ism_id, str(self.md_user_spi.sub_map)))
            return None


if __name__ == '__main__':

    # cc = CtpCmd('fasfjao-dfoajifo-12', CmdContent(instrument_id='dfas', price=12, volume=1, offset=1, direction=0))
    #
    # ccl = CtpCmdList()
    # ccl.cmd_dict['first_cmd'] = cc
    #
    # ccl.dump_cmd_dict_to_json_file()
    #
    # ccl.cmd_dict = {}
    # ccl.update_cmd_dict_by_local_json_file()
    #
    #
    # json.dumps(dict)

    mctp = MyCtp(ctp_login_info=ctp_login_info_sim)
    mctp.login()
    mctp.mmc.sub_rt_data(['m2101'])
    # print(mctp.ctp_spi.ccl.print_order_info())

    time.sleep(500)

    while True:
        if mctp.ctp_spi.login_success:
            mctp.pack_order_action('1x-703134750x1116093715x2')
            mctp.req_order_field_insert(
                instrument_id='m2009',
                price=2700,
                volume=1,
                offset='0',
                direction='b')
            # mctp.ctp_spi.login_success = False

            # 撤
            # mctp.req_order_action(mctp.ctp_spi.ccl.cmd_dict[list(mctp.ctp_spi.ccl.cmd_dict.keys())[0]].cmd_id)

            # 查
            # r = req_qry_investor_position('m2009')
            r = mctp.req_investor_position_all()
            logger.debug('登录成功！')

        time.sleep(2)
        logger.debug(str(mctp.ctp_spi.ccl.cmd_dict))

        # msg = get_current_datetime_str() + ':一次循环完成'
        # logger.debug(get_current_datetime_str() + ':一次循环完成')

