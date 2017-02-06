# -*- coding: utf-8 -*-

import dqn_agent_nature
import make_dataset
import copy
import csv
import numpy as np
import talib as ta
import pyximport
pyximport.install()
import cyfuncs
import tools


    
class Stock_agent():
    
    def __init__(self,agent,action_split_number):
    
        #agent = dqn_agent_nature.dqn_agent()
        self.Agent = agent
        self.stock = 0
        self.havestock = 0
        self.action = 0
        self.money = 1000000
        self.property =0
        self.buyprice = 0
        self.ave_buyprice = 0.0#平均取得単価
        self.sell_ratio = 0.0#売却時に何割の株を売ったか
        self.money_ratio = 1.0#総資産に対する現金の割合
        self.stock_ratio = 0.0#総資産に対する株式の割合
        
        self.action_split_number = action_split_number
        
    def observe_norm(self,env):
        '''
        env[0]: close price
        env[1]: volume
        env[2]: ema1
        env[3]: ema2
        env[4]: rsi
        env[5]: slowk
        env[6]: slowd
        env[7]: wllliamR
        '''
        
        min_price = np.min(env[0])
        max_price = np.max(env[0])
        env[0]=cyfuncs.normalizationArray(env[0],min_price,max_price)
        
        minv = np.min(env[1])
        maxv = np.max(env[1])
        env[1] = cyfuncs.normalizationArray(env[1],minv,maxv)
        
        env[2] = cyfuncs.normalizationArray(env[2],min_price,max_price)
        env[3]=cyfuncs.normalizationArray(env[3],min_price,max_price)
        
        env[4]=cyfuncs.normalizationArray(env[4],0,100)
        env[5]=cyfuncs.normalizationArray(env[5],0,100)
        env[6]=cyfuncs.normalizationArray(env[6],0,100)
        
        env[7]=cyfuncs.normalizationArray(env[7],-100,0)
        
    def observe_norm_new(self,env):
        '''
        env[0]: close price
        env[1]: volume
        env[2]: ema1
        env[3]: ema2
        env[4]: rsi
        env[5]: slowk
        env[6]: slowd
        env[7]: wllliamR
        '''
        env[0]=cyfuncs.normalizationArray_new(env[0])
        env[1]=cyfuncs.normalizationArray_new(env[1])
        env[2]=cyfuncs.normalizationArray_new(env[2])
        env[3]=cyfuncs.normalizationArray_new(env[3])
        env[4]=cyfuncs.normalizationArray_new(env[4])
        env[5]=cyfuncs.normalizationArray_new(env[5])
        env[6]=cyfuncs.normalizationArray_new(env[6])
        env[7]=cyfuncs.normalizationArray_new(env[7])
        
    def get_reward(self, last_action, nowprice ,buyprice):
        
        if (last_action == 0) or (last_action == 1):

            return 0
            
        elif last_action == -1:
            
            return float(nowprice - buyprice) / buyprice
        
    def get_reward_aveprice(self, last_action, nowprice, ave_buyprice,sell_ratio):
        if (last_action == 0) or (last_action == 1):
            return 0
            
        if ave_buyprice == 0:
            return 0
        
        elif last_action == -1:
            return float(nowprice - ave_buyprice)*sell_ratio / ave_buyprice
        
    def get_prospect_profit(self,havestock, nowprice, buyprice):
        #株を持っている場合の見込み利益を返す
        if havestock == 0:
            return 0
        elif havestock == 1:
            
            return float(nowprice - buyprice) / buyprice
        

    def calcstocks(self,money, price):
        i = 0
        _sum = 0
        while _sum <= money:
            i = i + 1
            _sum = 100 * price * i
            
        return 100 * (i - 1)
    
    def trading(self,term, price, traindata):
        #print term
        #print traindata
        #print traindata.shape
        start_p = self.money
        end_p = 0
        if price == -1:
            return 'error'
            
        for i in xrange(term - 1,len(price)):
            #print i,i-term
            observation = copy.deepcopy(traindata[:,i-term+1:i+1])
            #直近の期間で正規化
            self.observe_norm(observation)
            
            prospect_profit = self.get_prospect_profit(self.havestock,price[i],self.ave_buyprice)
            agent_status = np.array([self.havestock,prospect_profit,self.money_ratio,self.stock_ratio])
            observation = observation.reshape(1,-1)#一次元配列に変形
            observation = np.array([np.r_[observation[0], agent_status]])
            #print observation
            reward = self.get_reward_aveprice(self.action, price[i-1], self.ave_buyprice,self.sell_ratio)
            #print self.ave_buyprice
            if i == (term - 1):
                #print 'agent start!'
                Q_action = self.Agent.agent_start(observation)
            elif i == (len(price) - 1):
                #print 'agent end!'
                Q_action = self.Agent.agent_end(reward)
                Q_action = 0
            else:
                #print 'agent step'
                Q_action = self.Agent.agent_step(reward, observation)
                
            
            if Q_action > 0:#buy_pointのとき
                buy_ratio = float(Q_action) / self.action_split_number
                s = self.calcstocks(self.money * buy_ratio, price[i])#現在の所持金で買える株数を計算
                
                #現在の所持金で株が買える
                if (s > 0):
                    self.havestock = 1
                    self.action = 1
                    if self.stock == 0:
                        #ave_buypriceをリセット
                        self.ave_buyprice = 0
                        
                    #ave_buypriceを計算
                    self.ave_buyprice = (self.ave_buyprice * self.stock + price[i] * s) / (self.stock + s)
                    self.stock += s
                    self.buyprice = price[i]
                    self.money = self.money - s * self.buyprice
                else:
                    
                    self.action = 0
                    
            elif Q_action < 0:#sell_pointのとき
                if self.havestock == 1:#株を持っているなら
                    self.action = -1
                    
                    self.sell_ratio = float(abs(Q_action)) / self.action_split_number
                    sell_stocks = int(self.stock / self.sell_ratio)
                    if sell_stocks > self.stock:
                        sell_stocks = self.stock
                        self.sell_ratio = 1.0
                        
                    self.money = self.money + sell_stocks * price[i]
                    self.stock = self.stock - sell_stocks
                    
                    
                    if self.stock == 0:
                        self.havestock = 0

                    #self.buyprice = 0
                else:#株を持っていないなら
                    
                    self.action = 0
                    
                    
            else:#no_operationのとき
                
                self.action = 0
                
            #print self.action
            self.property = self.stock * price[i] + self.money
            self.money_ratio = float(self.money) / self.property
            self.stock_ratio = float(self.stock)*price[i] / self.property
            end_p = self.property#最終総資産
            
        profit_ratio = float((end_p - start_p) / start_p) * 100
        
        return profit_ratio

    def trading_test(self,term, price, testdata):
        #trading()の総資産推移や売買履歴を出力版
        start_p = self.money
        end_p = 0
        if price == -1:
            return 'error'
            
        proper = []
        order = []
        stocks = []
        price_data = []
        ave_buyprice_list = []
        reward_list = []
        Q_list = []
        
        for i in xrange(term - 1,len(price)):
            #print i,i-term
            observation = copy.deepcopy(testdata[:,i-term+1:i+1])
            #直近の期間で正規化
            self.observe_norm(observation)
            
            prospect_profit = self.get_prospect_profit(self.havestock,price[i],self.buyprice)
            agent_status = np.array([self.havestock,prospect_profit,self.money_ratio,self.stock_ratio])
            observation = observation.reshape(1,-1)#一次元配列に変形
            observation = np.array([np.r_[observation[0], agent_status]])
            #print observation
            reward = self.get_reward_aveprice(self.action, price[i-1], self.ave_buyprice,self.sell_ratio)
            #print self.ave_buyprice
            if i == (term - 1):
                #print 'agent start!'
                Q_action = self.Agent.agent_start(observation)
            elif i == (len(price) - 1):
                #print 'agent end!'
                Q_action = self.Agent.agent_end(reward)
                Q_action = 0
            else:
                #print 'agent step'
                Q_action = self.Agent.agent_step(reward, observation)
                
            price_data.append(price[i])
            
            Q_list.append(self.Agent.Q_recent.tolist())
            
            if Q_action > 0:#buy_pointのとき
                buy_ratio = float(Q_action) / self.action_split_number
                s = self.calcstocks(self.money * buy_ratio, price[i])#現在の所持金で買える株数を計算
                
                #現在の所持金で株が買える
                if (s > 0):
                    self.havestock = 1
                    self.action = 1
                    order.append(1)
                    if self.stock == 0:
                        #ave_buypriceをリセット
                        self.ave_buyprice = 0
                        
                    #ave_buypriceを計算
                    self.ave_buyprice = (self.ave_buyprice * self.stock + price[i] * s) / (self.stock + s)
                    self.stock += s
                    self.buyprice = price[i]
                    self.money = self.money - s * self.buyprice
                else:
                    order.append(0)
                    self.action = 0
                    
            elif Q_action < 0:#sell_pointのとき
                if self.havestock == 1:#株を持っているなら
                    self.action = -1
                    order.append(-1)
                    self.sell_ratio = float(abs(Q_action)) / self.action_split_number
                    sell_stocks = int(self.stock / self.sell_ratio)
                    if sell_stocks > self.stock:
                        sell_stocks = self.stock
                        self.sell_ratio = 1.0
                        
                    self.money = self.money + sell_stocks * price[i]
                    self.stock = self.stock - sell_stocks
                    
                    
                    if self.stock == 0:
                        self.havestock = 0

                    #self.buyprice = 0
                else:#株を持っていないなら
                    order.append(0)
                    self.action = 0
                    
                    
            else:#no_operationのとき
                
                self.action = 0
                order.append(0)
            #print self.action
            self.property = self.stock * price[i] + self.money
            proper.append(self.property)
            stocks.append(self.stock)
            ave_buyprice_list.append(self.ave_buyprice)
            reward_list.append(reward)
            self.money_ratio = float(self.money) / self.property
            self.stock_ratio = float(self.stock)*price[i] / self.property
            end_p = self.property#最終総資産
            
        profit_ratio = float((end_p - start_p) / start_p) * 100
        
        return profit_ratio, proper, order, stocks, price_data, Q_list, ave_buyprice_list,reward_list
    
    def trading_evaluation(self,term, price, traindata, evaluation_freq, evaluater):
        
        #trading()の売買中に評価する版
        start_p = self.money
        end_p = 0
        if price == -1:
            return 'error'
            
        for i in xrange(term - 1,len(price)):
            #print i,i-term
            observation = copy.deepcopy(traindata[:,i-term+1:i+1])
            #直近の期間で正規化
            self.observe_norm(observation)

            prospect_profit = self.get_prospect_profit(self.havestock,price[i],self.ave_buyprice)
            agent_status = np.array([self.havestock,prospect_profit,self.money_ratio,self.stock_ratio])
            observation = observation.reshape(1,-1)#一次元配列に変形
            observation = np.array([np.r_[observation[0], agent_status]])
            #print observation
            reward = self.get_reward_aveprice(self.action, price[i-1], self.ave_buyprice,self.sell_ratio)
            #print self.ave_buyprice
            if i == (term - 1):
                #print 'agent start!'
                Q_action = self.Agent.agent_start(observation)
            elif i == (len(price) - 1):
                #print 'agent end!'
                Q_action = self.Agent.agent_end(reward)
                Q_action = 0
            else:
                #print 'agent step'
                Q_action = self.Agent.agent_step(reward, observation)
                
            
            if Q_action > 0:#buy_pointのとき
                buy_ratio = float(Q_action) / self.action_split_number
                s = self.calcstocks(self.money * buy_ratio, price[i])#現在の所持金で買える株数を計算
                
                #現在の所持金で株が買える
                if (s > 0):
                    self.havestock = 1
                    self.action = 1
                    if self.stock == 0:
                        #ave_buypriceをリセット
                        self.ave_buyprice = 0
                        
                    #ave_buypriceを計算
                    self.ave_buyprice = (self.ave_buyprice * self.stock + price[i] * s) / (self.stock + s)
                    self.stock += s
                    self.buyprice = price[i]
                    self.money = self.money - s * self.buyprice
                else:
                    
                    self.action = 0
                    
            elif Q_action < 0:#sell_pointのとき
                if self.havestock == 1:#株を持っているなら
                    self.action = -1
                    
                    self.sell_ratio = float(abs(Q_action)) / self.action_split_number
                    sell_stocks = int(self.stock / self.sell_ratio)
                    if sell_stocks > self.stock:
                        sell_stocks = self.stock
                        self.sell_ratio = 1.0
                        
                    self.money = self.money + sell_stocks * price[i]
                    self.stock = self.stock - sell_stocks
                    
                    
                    if self.stock == 0:
                        self.havestock = 0

                    #self.buyprice = 0
                else:#株を持っていないなら
                    
                    self.action = 0
                    
                    
            else:#no_operationのとき
                
                self.action = 0
                
            #print self.action
            self.property = self.stock * price[i] + self.money
            self.money_ratio = float(self.money) / self.property
            self.stock_ratio = float(self.stock)*price[i] / self.property
            end_p = self.property#最終総資産
            
            #evaluation Phase
            if (self.Agent.time % evaluation_freq) == 0 and (self.Agent.time != 0):
                print 'time step:',self.Agent.time
                eval_model = self.Agent.DQN.get_model_copy()
                evaluater.eval_performance(eval_model)
                evaluater.get_epsilon(self.Agent.epsilon)
                evaluater.save_eval_result()
                self.Agent.DQN.save_model(evaluater.result_folder,self.Agent.time)
                
                
        profit_ratio = float((end_p - start_p) / start_p) * 100
        
        return profit_ratio
    
    def trading_tsne(self,term, price, testdata):
        #trading()の総資産推移や売買履歴を出力版
        start_p = self.money
        end_p = 0
        if price == -1:
            return 'error'
            
        proper = []
        order = []
        stocks = []
        price_data = []
        ave_buyprice_list = []
        reward_list = []
        Q_list = []
        #---------------------for tsne
        Q_action_list = []
        prospect_profit_list = []
        havestock_list = []
        money_ratio_list = []
        #----------------------
        
        
        for i in xrange(term - 1,len(price)):
            #print i,i-term
            observation = copy.deepcopy(testdata[:,i-term+1:i+1])
            #直近の期間で正規化
            self.observe_norm(observation)
            
            prospect_profit = self.get_prospect_profit(self.havestock,price[i],self.buyprice)
            agent_status = np.array([self.havestock,prospect_profit,self.money_ratio,self.stock_ratio])
            observation = observation.reshape(1,-1)#一次元配列に変形
            observation = np.array([np.r_[observation[0], agent_status]])
            #print observation
            reward = self.get_reward_aveprice(self.action, price[i-1], self.ave_buyprice,self.sell_ratio)
            #print self.ave_buyprice
            if i == (term - 1):
                #print 'agent start!'
                Q_action = self.Agent.agent_start(observation)
            elif i == (len(price) - 1):
                #print 'agent end!'
                Q_action = self.Agent.agent_end(reward)
                Q_action = 0
            else:
                #print 'agent step'
                Q_action = self.Agent.agent_step(reward, observation)
                
            price_data.append(price[i])
            
            Q_list.append(self.Agent.Q_recent.tolist())
            
            if i != (len(price) - 1):
                #終端でなければ
                Q_action_list.append(Q_action)
                prospect_profit_list.append(prospect_profit)
                havestock_list.append(self.havestock)
                money_ratio_list.append(self.money_ratio)
            
            if Q_action > 0:#buy_pointのとき
                buy_ratio = float(Q_action) / self.action_split_number
                s = self.calcstocks(self.money * buy_ratio, price[i])#現在の所持金で買える株数を計算
                
                #現在の所持金で株が買える
                if (s > 0):
                    self.havestock = 1
                    self.action = 1
                    order.append(1)
                    if self.stock == 0:
                        #ave_buypriceをリセット
                        self.ave_buyprice = 0
                        
                    #ave_buypriceを計算
                    self.ave_buyprice = (self.ave_buyprice * self.stock + price[i] * s) / (self.stock + s)
                    self.stock += s
                    self.buyprice = price[i]
                    self.money = self.money - s * self.buyprice
                else:
                    order.append(0)
                    self.action = 0
                    
            elif Q_action < 0:#sell_pointのとき
                if self.havestock == 1:#株を持っているなら
                    self.action = -1
                    order.append(-1)
                    self.sell_ratio = float(abs(Q_action)) / self.action_split_number
                    sell_stocks = int(self.stock / self.sell_ratio)
                    if sell_stocks > self.stock:
                        sell_stocks = self.stock
                        self.sell_ratio = 1.0
                        
                    self.money = self.money + sell_stocks * price[i]
                    self.stock = self.stock - sell_stocks
                    
                    
                    if self.stock == 0:
                        self.havestock = 0

                    #self.buyprice = 0
                else:#株を持っていないなら
                    order.append(0)
                    self.action = 0
                    
                    
            else:#no_operationのとき
                
                self.action = 0
                order.append(0)
            #print self.action
            self.property = self.stock * price[i] + self.money
            proper.append(self.property)
            stocks.append(self.stock)
            ave_buyprice_list.append(self.ave_buyprice)
            reward_list.append(reward)
            self.money_ratio = float(self.money) / self.property
            self.stock_ratio = float(self.stock)*price[i] / self.property
            end_p = self.property#最終総資産
            
        profit_ratio = float((end_p - start_p) / start_p) * 100
        
        return profit_ratio, proper, order, stocks, price_data, Q_list, ave_buyprice_list,reward_list,Q_action_list,prospect_profit_list,havestock_list,money_ratio_list
        
class StockMarket():
    
    def __init__(self,END_TRADING_DAY,START_TEST_DAY,u_vol=False,u_ema=False,u_rsi=False,u_macd=False,u_stoch=False,u_wil=False):
    
        
        
        self.u_vol = u_vol
        self.u_ema = u_ema
        self.u_rsi = u_rsi
        self.u_macd = u_macd
        self.u_stoch = u_stoch
        self.u_wil = u_wil
        
        self.END_TRADING_DAY = END_TRADING_DAY
        self.START_TEST_DAY = START_TEST_DAY
        
    def get_trainData(self,filename,input_num,stride=1):
        
        all_data = []
        traindata = []
        
        #print tech_name
        filepath = "./stockdata/%s" % filename
        _time,_open,_max,_min,_close,_volume,_keisu,_shihon = self.readfile(filepath)

        #start_test_dayでデータセットを分割
        try:
            iday = _time.index(self.END_TRADING_DAY)
        except:
            #print "can't find start_test_day"
            #start_test_dayが見つからなければ次のファイルへ
            raise Exception('cannot find start_test_day')            
        
        cutpoint = iday - input_num + 1
        
        rec = copy.copy(_close)
        price_min = min(_close[:cutpoint])
        price_max = max(_close[:cutpoint])
        #make_dataset.normalizationArray(rec,price_min,price_max)
        all_data.append(rec)
        
        
        if self.u_vol == True:
            vol_list = _volume
            t_min = min(vol_list[:cutpoint])
            t_max = max(vol_list[:cutpoint])
            #make_dataset.normalizationArray(vol_list,t_min,t_max)
            all_data.append(vol_list)
            
        if self.u_ema == True:
            ema_list1 = ta.EMA(np.array(_close, dtype='f8'), timeperiod = 10)
            ema_list2 = ta.EMA(np.array(_close, dtype='f8'), timeperiod = 25)
            ema_list1 = np.ndarray.tolist(ema_list1)
            ema_list2 = np.ndarray.tolist(ema_list2)
            t_min = min(_close[:cutpoint])
            t_max = max(_close[:cutpoint])
            
            #make_dataset.normalizationArray(ema_list1,t_min,t_max)
            #make_dataset.normalizationArray(ema_list2,t_min,t_max)
            all_data.append(ema_list1)
            all_data.append(ema_list2)
            
        if  self.u_rsi == True:
            rsi_list = ta.RSI(np.array(_close, dtype='f8'), timeperiod = 14)
            rsi_list = np.ndarray.tolist(rsi_list)
            
            #make_dataset.normalizationArray(rsi_list,0,100)
            all_data.append(rsi_list)
            
        if self.u_macd == True:
            macd_list,signal,hist = ta.MACD(np.array(_close, dtype='f8'), fastperiod = 12, slowperiod = 26, signalperiod = 9)
            macd_list = np.ndarray.tolist(macd_list)
            signal = np.ndarray.tolist(signal)
            
            t_min = np.nanmin(macd_list[:cutpoint])
            t_max = np.nanmax(macd_list[:cutpoint])
            if (t_min == np.nan) or (t_max == np.nan):
                print 'np.nan error'
                raise Exception('np.nan error')
            #make_dataset.normalizationArray(macd_list,t_min,t_max)
            #make_dataset.normalizationArray(signal,t_min,t_max)
            all_data.append(macd_list)
            all_data.append(signal)
            
        if self.u_stoch == True:
            slowk,slowd = ta.STOCH(np.array(_max, dtype='f8'),np.array(_min, dtype='f8'),np.array(_close, dtype='f8'), fastk_period = 5,slowk_period=3,slowd_period=3)
            slowk = np.ndarray.tolist(slowk)
            slowd = np.ndarray.tolist(slowd)
            #make_dataset.normalizationArray(slowk,0,100)
            #make_dataset.normalizationArray(slowd,0,100)
            all_data.append(slowk)
            all_data.append(slowd)
            
        if self.u_wil == True:
            will = ta.WILLR(np.array(_max, dtype='f8'),np.array(_min, dtype='f8'),np.array(_close, dtype='f8'), timeperiod = 14)
            will = np.ndarray.tolist(will)
            #make_dataset.normalizationArray(will,-100,0)
            all_data.append(will)
        
        all_data = np.array(all_data)
        
        traindata = all_data[:,:cutpoint]
        trainprice = _close[:cutpoint]
        
        #テクニカル指標のパラメータ日数分最初を切る
        traindata = traindata[:,30:]
        trainprice = trainprice[30:]
        
        return traindata,trainprice
    
    def get_testData(self,filename,input_num,stride=1):
        
        all_data = []
        testdata = []
        
        #print tech_name
        filepath = "./stockdata/%s" % filename
        _time,_open,_max,_min,_close,_volume,_keisu,_shihon = self.readfile(filepath)

        #start_test_dayでデータセットを分割
        try:
            iday = _time.index(self.START_TEST_DAY)
        except:
            #print "can't find start_test_day"
            #start_test_dayが見つからなければ次のファイルへ
            raise Exception('cannot find start_test_day')            
        
        cutpoint = iday - input_num + 1
        
        rec = copy.copy(_close)
        price_min = min(_close[:cutpoint])
        price_max = max(_close[:cutpoint])
        #make_dataset.normalizationArray(rec,price_min,price_max)
        all_data.append(rec)
        
        
        if self.u_vol == True:
            vol_list = _volume
            t_min = min(vol_list[:cutpoint])
            t_max = max(vol_list[:cutpoint])
            #make_dataset.normalizationArray(vol_list,t_min,t_max)
            all_data.append(vol_list)
            
        if self.u_ema == True:
            ema_list1 = ta.EMA(np.array(_close, dtype='f8'), timeperiod = 10)
            ema_list2 = ta.EMA(np.array(_close, dtype='f8'), timeperiod = 25)
            ema_list1 = np.ndarray.tolist(ema_list1)
            ema_list2 = np.ndarray.tolist(ema_list2)
            t_min = min(_close[:cutpoint])
            t_max = max(_close[:cutpoint])
            
            #make_dataset.normalizationArray(ema_list1,t_min,t_max)
            #make_dataset.normalizationArray(ema_list2,t_min,t_max)
            all_data.append(ema_list1)
            all_data.append(ema_list2)
            
        if  self.u_rsi == True:
            rsi_list = ta.RSI(np.array(_close, dtype='f8'), timeperiod = 14)
            rsi_list = np.ndarray.tolist(rsi_list)
            
            #make_dataset.normalizationArray(rsi_list,0,100)
            all_data.append(rsi_list)
            
        if self.u_macd == True:
            macd_list,signal,hist = ta.MACD(np.array(_close, dtype='f8'), fastperiod = 12, slowperiod = 26, signalperiod = 9)
            macd_list = np.ndarray.tolist(macd_list)
            signal = np.ndarray.tolist(signal)
            
            t_min = np.nanmin(macd_list[:cutpoint])
            t_max = np.nanmax(macd_list[:cutpoint])
            if (t_min == np.nan) or (t_max == np.nan):
                print 'np.nan error'
                raise Exception('np.nan error')
            #make_dataset.normalizationArray(macd_list,t_min,t_max)
            #make_dataset.normalizationArray(signal,t_min,t_max)
            all_data.append(macd_list)
            all_data.append(signal)
            
        if self.u_stoch == True:
            slowk,slowd = ta.STOCH(np.array(_max, dtype='f8'),np.array(_min, dtype='f8'),np.array(_close, dtype='f8'), fastk_period = 5,slowk_period=3,slowd_period=3)
            slowk = np.ndarray.tolist(slowk)
            slowd = np.ndarray.tolist(slowd)
            #make_dataset.normalizationArray(slowk,0,100)
            #make_dataset.normalizationArray(slowd,0,100)
            all_data.append(slowk)
            all_data.append(slowd)
            
        if self.u_wil == True:
            will = ta.WILLR(np.array(_max, dtype='f8'),np.array(_min, dtype='f8'),np.array(_close, dtype='f8'), timeperiod = 14)
            will = np.ndarray.tolist(will)
            #make_dataset.normalizationArray(will,-100,0)
            all_data.append(will)
        
        all_data = np.array(all_data)
        
        testdata = all_data[:,cutpoint:]
        testprice = _close[cutpoint:]
        
        return testdata,testprice
    
    def readfile(self,filename):
        _time = []
        _open = []
        _max = []
        _min = []
        _close = []
        _volume = []
        _keisu = []
        _shihon = []
        f = open(filename,'rb')
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            #print row
            #print row[0]
            _time.append(float(row[0]))
            _open.append(float(row[1])*float(row[6]))
            _max.append(float(row[2])*float(row[6]))
            _min.append(float(row[3])*float(row[6]))
            _close.append(float(row[4])*float(row[6]))
            _volume.append(float(row[5])*float(row[6]))
            _keisu.append(float(row[6]))
            _shihon.append(float(row[7]))
        
        f.close()   
        return _time,_open,_max,_min,_close,_volume,_keisu,_shihon
