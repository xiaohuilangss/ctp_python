# encoding=utf-8
import logging
import time

import thostmduserapi as mdapi

from Server.futures.futures_account_info.account_info import ctp_login_info, ctp_login_info_sim
from my_config.log import MyLog
from sdk.MyTimeOPT import get_current_datetime_str

logger_eml = MyLog('md_ctp_eml', file_level=logging.DEBUG).logger


class CFtdcMdSpi(mdapi.CThostFtdcMdSpi):

    def __init__(self, tapi, ctp_login_info):
        mdapi.CThostFtdcMdSpi.__init__(self)
        self.ctp_login_info = ctp_login_info
        self.tapi = tapi
        self.sub_map = {}

    def OnFrontConnected(self) -> "void":
        logger_eml.debug("OnFrontConnected")
        try:
            loginfield = mdapi.CThostFtdcReqUserLoginField()
            loginfield.BrokerID = self.ctp_login_info['broker_id']
            loginfield.UserID = self.ctp_login_info['user_id']
            loginfield.Password = self.ctp_login_info['password']
            # loginfield.UserProductInfo = "python dll"
            self.tapi.ReqUserLogin(loginfield, 0)
        except Exception as e:
            logger_eml.exception('登录front出错！具体：%s' % str(e))

    def OnRspUserLogin(self, pRspUserLogin: 'CThostFtdcRspUserLoginField', pRspInfo: 'CThostFtdcRspInfoField',
                       nRequestID: 'int', bIsLast: 'bool') -> "void":
        logger_eml.debug(
            f"OnRspUserLogin, SessionID={pRspUserLogin.SessionID},ErrorID={pRspInfo.ErrorID},ErrorMsg={pRspInfo.ErrorMsg}")

    def OnRtnDepthMarketData(self, pDepthMarketData: 'CThostFtdcDepthMarketDataField') -> "void":
        # logger_eml.debug("OnRtnDepthMarketData")
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
                'last_price': pDepthMarketData.LastPrice
            }

        except Exception as e:
            logger_eml.exception('获取rt futures数据失败！具体原因：\n%s' % str(e))

    def OnRspSubMarketData(self, pSpecificInstrument: 'CThostFtdcSpecificInstrumentField',
                           pRspInfo: 'CThostFtdcRspInfoField', nRequestID: 'int', bIsLast: 'bool') -> "void":
        logger_eml.debug("OnRspSubMarketData")
        logger_eml.debug("InstrumentID=%s" % pSpecificInstrument.InstrumentID)
        logger_eml.debug("ErrorID=%s" % pRspInfo.ErrorID)
        logger_eml.debug("ErrorMsg=%s" % pRspInfo.ErrorMsg)


class MyMdCpt:
    def __init__(self, login_ctp_info):
        self.login_ctp_info = login_ctp_info
        self.md_user_api = mdapi.CThostFtdcMdApi_CreateFtdcMdApi()
        self.md_user_spi = CFtdcMdSpi(self.md_user_api, ctp_login_info=ctp_login_info)

    def sub_rt_data(self, sub_id_list):
        ret = self.md_user_spi.tapi.SubscribeMarketData([id.encode('utf-8') for id in sub_id_list], len(sub_id_list))

    def login(self):
        self.md_user_api.RegisterFront(ctp_login_info['front_addr_data'])
        self.md_user_api.RegisterSpi(self.md_user_spi)
        self.md_user_api.Init()


if __name__ == '__main__':
    mmc = MyMdCpt(ctp_login_info_sim)
    mmc.login()
    mmc.sub_rt_data(["zn2012"])
    while True:
        print('%s\n%s' % (get_current_datetime_str(), str(mmc.md_user_spi.sub_map)))
        time.sleep(1)