import backtrader as bt
import pandas as pd
import datetime
import os

# [新增] 強制設定 matplotlib 後端，避免與 Backtrader 衝突
import matplotlib
matplotlib.use('TkAgg') 
import matplotlib.pyplot as plt

class ExcelSignalStrategy(bt.Strategy):
    params = (('df_signals', None),)

    def __init__(self):
        # 1. 取得傳入的 DataFrame
        raw_df = self.params.df_signals.copy()
        
        # 2. 轉換日期格式
        raw_df['Date'] = pd.to_datetime(raw_df['Date'])
        
        # [防護] 去除重複日期，解決 ValueError: The truth value of a Series is ambiguous
        raw_df = raw_df.drop_duplicates(subset=['Date'], keep='last')
        
        # 3. 設定索引
        raw_df.set_index('Date', inplace=True)
        
        self.df_signals = raw_df
        self.dataclose = self.datas[0].close

    def next(self):
        current_date = self.datas[0].datetime.date(0)
        current_date = pd.Timestamp(current_date)

        if current_date in self.df_signals.index:
            try:
                row = self.df_signals.loc[current_date]
                # 再次確保是單一列
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[-1]
                
                action = row['Action']
                shares_delta = float(row['Shares_Delta'])

                if action == 'BUY':
                    self.buy(size=shares_delta)
                elif action == 'SELL':
                    self.sell(size=abs(shares_delta))
                    
            except Exception as e:
                print(f"⚠️ {current_date.date()} 執行訊號失敗: {e}")

def plot_backtest(ticker, excel_path, auto_open=True):
    """
    ticker: 股票代碼
    excel_path: Excel 路徑
    auto_open: 存檔後是否彈出視窗
    """
    # [關鍵修正 1] 強制清空所有舊圖表，避免 ".!canvas" 錯誤
    plt.close('all') 
    
    print(f"\n{'='*40}")
    print(f"📊 正在處理 {ticker} ...")
    
    if not os.path.exists(excel_path):
        print(f"❌ 找不到檔案，跳過: {excel_path}")
        return

    df_signals = pd.read_excel(excel_path)
    
    if df_signals.empty:
        print("⚠️ Excel 中沒有交易紀錄，跳過。")
        return

    cerebro = bt.Cerebro()
    cerebro.addstrategy(ExcelSignalStrategy, df_signals=df_signals)

    # 準備數據
    try:
        start_date = pd.to_datetime(df_signals['Date'].min())
        end_date = pd.to_datetime(df_signals['Date'].max())
        
        import yfinance as yf
        # 前後各加 15 天
        data_start = start_date - datetime.timedelta(days=15)
        data_end = end_date + datetime.timedelta(days=15)
        
        print(f"📥 下載 K 線: {data_start.date()} ~ {data_end.date()}")
        data_df = yf.download(ticker, start=data_start, end=data_end, progress=False)
        
        if data_df.empty:
            print("❌ 無法下載股價數據。")
            return

        if isinstance(data_df.columns, pd.MultiIndex):
            data_df.columns = data_df.columns.get_level_values(0)
        
        data_df.columns = [c.lower() for c in data_df.columns]
        data_df = data_df.rename(columns={'open':'open', 'high':'high', 'low':'low', 'close':'close', 'volume':'volume'})
        
        data = bt.feeds.PandasData(dataname=data_df)
        cerebro.adddata(data)
        cerebro.broker.setcash(100000) 

        # 執行 Backtrader
        cerebro.run()
        
        # 繪圖並存檔
        print("🎨 繪製並存檔中...")
        # iplot=False 是關鍵，不要讓 Backtrader 自己搶著彈窗
        figures = cerebro.plot(style='candlestick', barup='green', bardown='red', volume=True, iplot=False)
        
        if figures and len(figures) > 0 and len(figures[0]) > 0:
            fig = figures[0][0]
            fig.set_size_inches(16, 9)
            
            save_path = f"results/{ticker}_backtrader_chart.png"
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ {ticker} 圖表已儲存至: {save_path}")

            if auto_open:
                print(f"👀 正在顯示 {ticker} 圖表 (請關閉視窗以繼續)...")
                plt.show() # 這會暫停程式，直到視窗關閉
            else:
                plt.close(fig) # 如果不顯示，手動關閉釋放記憶體
        else:
            print("⚠️ 無法產生圖表物件")
            
    except Exception as e:
        print(f"❌ {ticker} 繪圖發生錯誤: {e}")
        # 發生錯誤時也要清空，確保不影響下一張圖
        plt.close('all')

if __name__ == "__main__":
    # 設定關注清單
    TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"] 
    # TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA"]
    
    print(f"🚀 開始批量繪製圖表任務，共 {len(TICKERS)} 檔")
    
    for ticker in TICKERS:
        excel_path = f"results/{ticker}_backtest_results.xlsx"
        
        # 建議先用 auto_open=True 測試第一張，沒問題後改成 False 跑全自動
        plot_backtest(ticker, excel_path, auto_open=False)
        
    print("\n🎉 所有圖表處理完成！")