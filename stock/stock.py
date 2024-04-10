from statsmodels.regression.rolling import RollingOLS
import pandas_datareader.data as web
import matplotlib.pyplot as plt
import statsmodels.api as sm
import yfinance as yfin
import yahoo_fin.options as ops
from yahoo_fin.stock_info import get_data
import pyotp
import robin_stocks as robin
import yahoo_fin.stock_info as si
import pandas as pd
import numpy as np
import datetime as dt
import math
import os
import io
from pytz import timezone
from pandas_datareader import data as wb
from scipy.stats import norm
import pyetrade

class Stock():

    def __init__ (self, _):
        _ = self._

    def getLowestPrice(ticker, expiration_date):
        yfin.pdr_override()
        data = pd.DataFrame()
        data[ticker] = wb.get_data_yahoo(ticker, start='2014-1-1')['Adj Close']
        log_returns = np.log(1 + data.pct_change())
        #  log_returns.tail()
        #  data.plot(figsize=(10,6));
        #  log_returns.plot(figsize = (10,6))
        u = log_returns.mean()
        var = log_returns.var()
        #  var
        drift = u - (0.5 * var)
        #  drift
        stdev = log_returns.std()
        #  stdev
        # type(drift)

        # type(stdev)
        np.array(drift)
        #  drift.values
        #  stdev.values
        norm.ppf(0.95)
        x = np.random.rand(10,2)
        #  x
        norm.ppf(x)
        Z = norm.ppf(np.random.rand(10, 2))
        #  Z
        t_intervals = 1000
        iterations = 10
        daily_returns = np.exp(drift.values + stdev.values * norm.ppf(np.random.rand(t_intervals, iterations)))
        daily_returns
        S0 = data.iloc[-1]
        #  S0
        price_list = np.zeros_like(daily_returns)
        #  price_list
        price_list[0] = S0
        #  price_list
        for t in range(1, t_intervals):
            price_list[t] = price_list[t-1] * daily_returns[t]
        #  price_list

        #calculate the number of days between today and expiration date
        delta = dt.datetime.strptime(expiration_date, f'%Y-%m-%d') - dt.datetime.today()
        days = delta.days
        #find lowest price
        lowest = price_list[days-1][0]
        for i in range(price_list.shape[1]):
            #for k in range(len(price_list.rows))
            if (price_list[days-1][i] < lowest):
                lowest = price_list[days-1][i]
        return(lowest)
        #find highest price
        # highest = price_list[999][0]
        # for i in range(price_list.shape[1]):
        #   if(price_list[999][i] > highest):
        #     highest = price_list[999][i]
        # highest
        # plt.figure(figsize = (10,6))
        # plt.plot(price_list)

        #Gets all the options data for a stock - adds useful columns below


    def getOptions(ticker):

        out = pd.DataFrame()

        today_obj = dt.datetime.strptime(dt.datetime.now().astimezone(timezone('America/Chicago')).strftime(f'%Y-%m-%d'), f"%Y-%m-%d")
        today_str = today_obj.strftime(f'%Y-%m-%d')

        days_from_today = (today_obj + dt.timedelta(days=120)).strftime(f'%Y-%m-%d')

        fundamentals = robin.robinhood.stocks.get_fundamentals(ticker)[0]
        if (fundamentals == None or 'ex_dividend_date' not in fundamentals.keys() or fundamentals['ex_dividend_date'] == None):
            return out

        ex_div_date = fundamentals['ex_dividend_date']
        #days_to_exdividend includes today
        days_to_exdividend = (dt.datetime.strptime(ex_div_date, f'%Y-%m-%d') - today_obj).days

        #choose the days to exdividend
        if (ex_div_date <= today_str or days_to_exdividend >= 7):
            return out

        #gets only option dates that are feasible
        options_data = robin.robinhood.options.get_chains(ticker)
        if (options_data == None):
            return out

        expiration_dates =  [e for e in options_data['expiration_dates'] if e <= days_from_today and e > ex_div_date and e > today_str ]
        stock_price = pd.to_numeric(robin.robinhood.stocks.get_latest_price(ticker)[0])
        qdiv = pd.to_numeric(fundamentals['dividend_yield'])*stock_price/400


        for expiration_date in expiration_dates:
            option_data = robin.robinhood.options.find_options_by_expiration(ticker,expiration_date,optionType='call')
            df = pd.json_normalize(option_data)
            strike_price = pd.to_numeric(df['strike_price'])
            #print(df.columns)
            try:
                df = df[['symbol', 'strike_price', 'ask_price', 'bid_price', 'volume', 'open_interest']]
                df['qdiv'] = qdiv
                df['ex_div_date'] = ex_div_date
                df['dtd'] = days_to_exdividend
                df['exp_date'] = expiration_date
                df['dte'] = (dt.datetime.strptime(expiration_date, f'%Y-%m-%d') - today_obj).days
                df['stock_price'] = pd.to_numeric(robin.robinhood.stocks.get_latest_price(ticker)[0])
                df['strike_price'] = pd.to_numeric(df['strike_price'])
                df['ask_price'] = pd.to_numeric(df['ask_price'])
                df['bid_price'] = pd.to_numeric(df['bid_price'])
                df.insert(4, 'mark_price', (df['ask_price'] + df['bid_price']) / 2)
                #Get both qdiv and call premium if wait until expiry
                df['annual_profit_perc'] = 365 * 100 * (df['qdiv'] + (df['mark_price'] + df['strike_price'] - df['stock_price'])) / (df['stock_price'] - df['mark_price']) / df['dte']
                #Get only the call premium if exercised early
                df['annual_profit_exer'] = 365 * 100 * (df['mark_price'] + df['strike_price'] - df['stock_price']) / (df['stock_price'] - df['mark_price']) / df['dtd']
                df['lowest_price'] = Stock.getLowestPrice(ticker, expiration_date)
                df['limit_price'] = df['stock_price'] - df['mark_price']
                out = pd.concat([out,df], ignore_index=True)
            except:
                print("Data is missing for " + ticker)
        #    print(out)

        #Can choose annual_profit (a percent) - profit_threshold will convert that to daily_profit_threshold
        annual_profit = 5
        annual_profit_exer = 5

        #Defining the thresholds
        dif_threshold = 0
        volume_threshold = 10
        daily_profit_threshold = annual_profit/365
        daily_profit_if_exer = annual_profit_exer/365
        open_interest_threshold = 100
        qdiv_threshold = 0.1

        #Returning the rows that meets the criteria
        if not out.empty:

            #If strike_price and stock_price are far enough from each other
            out = out[100 * (out['stock_price'] - out['strike_price']) / (out['stock_price']) >= dif_threshold]
        # else:
        #     return out
            #If stock is liquid enough
            #out = out[out['volume'] >= volume_threshold]
            out = out[out['open_interest'] >= open_interest_threshold]

            #If the sell call has extrinsic value greater than or equal to a percentage of the quarterly dividend
            out = out[(out['ask_price'] + out['bid_price']) / 2 + out['strike_price'] - out['stock_price'] >=  qdiv_threshold * out['qdiv']]

            #If daily profit percent will be enough
            out = out[100 * out['qdiv'] / out['strike_price'] / out['dte'] >= daily_profit_threshold]

            #If daily profit percent based on exercise will be enough
            out = out[100 * (out['mark_price'] + out['strike_price'] - out['stock_price']) / (out['stock_price'] - out['mark_price']) / out['dtd'] >= daily_profit_if_exer]

            #If the strike price is lower than the MC simulation's lowest predicted price
            #This is the last check since it is the most computationally expensive
            out = out[out['strike_price'] < out['lowest_price']]
        return(out)

    def getDataFrame():
        final = pd.DataFrame()
        tickers = ['FCX', 'PNC', 'HRL']#'AMT', 'PNC', 'HRL'
        #tickers = si.tickers_dow()
        #can add Nasdaq and SP600 here
        #sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        #sp500['Symbol'] = sp500['Symbol'].str.replace('.', '-')
        #tickers.extend(sp500['Symbol'].unique().tolist())   
        #tickers = (sp500['Symbol'].unique().tolist()) 
        print(tickers)
        #tickers.extend(pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0])
        #print(tickers)
        #tickers.extend(getTickers(7))
        #print(tickers)
        tickers = list(set(tickers))
        tickers.sort()

        count = 1
        for ticker in tickers:
            #print(count, ticker)
            count += 1
            out_options = Stock.getOptions(ticker)
            final = pd.concat([final, out_options], ignore_index=True)
            try:
                final = final.sort_values(by='annual_profit_perc', ascending=False)
            except:
                print(ticker + ' is giving an error.')
        return final.iloc[:3]

    def getSymbol(df):
        return df['symbol']
    

    def getExpiryDate(df):
        return df['exp_date']
    

    def getLimitPrice(df):
        return df['limit_price']
    

    def getStrikePrice(df):
        return df['strike_price']
    