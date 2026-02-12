import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import numpy as np
import os

class BenchmarkRunner:
    def __init__(self, ticker, start_date, end_date, agent_excel_path):
        self.ticker = ticker
        self.start = start_date
        self.end = end_date
        self.agent_path = agent_excel_path
        self.data = None
        self.results = pd.DataFrame()
        
    def fetch_data(self):
        """下載原始股價數據"""
        print(f"📥 下載 {self.ticker} 基準數據 ({self.start} ~ {self.end})...")
        # 多抓一點前面的資料以便計算 MA/MACD 的初始值
        download_start = pd.to_datetime(self.start) - pd.Timedelta(days=60)
        try:
            df = yf.download(self.ticker, start=download_start, end=self.end, progress=False)
            
            if df.empty:
                print(f"❌ 無法下載 {self.ticker} 數據")
                return

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            # 計算日報酬率 (Close to Close)
            df['Daily_Ret'] = df['Close'].pct_change()
            self.data = df
        except Exception as e:
            print(f"❌ 下載失敗: {e}")
            self.data = pd.DataFrame()
        
    def calc_buy_and_hold(self):
        if self.data is None or self.data.empty: return
        """策略 1: 買進持有 (Buy & Hold)"""
        mask = (self.data.index >= self.start) & (self.data.index <= self.end)
        df = self.data.loc[mask].copy()
        if df.empty: return
        
        df['Cum_Ret'] = (1 + df['Daily_Ret']).cumprod() - 1
        self.results['Buy & Hold'] = df['Cum_Ret']
        self.results.index = df.index

    def calc_sma_strategy(self, short_window=5, long_window=20):
        if self.data is None or self.data.empty: return
        """策略 2: 簡單移動平均線交叉"""
        df = self.data.copy()
        df['SMA_S'] = df['Close'].rolling(window=short_window).mean()
        df['SMA_L'] = df['Close'].rolling(window=long_window).mean()
        df['Signal'] = np.where(df['SMA_S'] > df['SMA_L'], 1, 0)
        df['Strategy_Ret'] = df['Signal'].shift(1) * df['Daily_Ret']
        
        mask = (df.index >= self.start) & (df.index <= self.end)
        df = df.loc[mask].copy()
        self.results['SMA'] = (1 + df['Strategy_Ret']).cumprod() - 1

    def calc_macd_strategy(self):
        if self.data is None or self.data.empty: return
        """策略 3: MACD 策略"""
        df = self.data.copy()
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=9, adjust=False).mean()
        
        df['Signal'] = np.where(macd > signal_line, 1, 0)
        df['Strategy_Ret'] = df['Signal'].shift(1) * df['Daily_Ret']
        
        mask = (df.index >= self.start) & (df.index <= self.end)
        df = df.loc[mask].copy()
        self.results['MACD'] = (1 + df['Strategy_Ret']).cumprod() - 1

    def calc_rsi_strategy(self, period=14):
        if self.data is None or self.data.empty: return
        """策略 4: RSI 逆勢策略"""
        df = self.data.copy()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['Signal'] = np.nan
        df.loc[df['RSI'] < 30, 'Signal'] = 1
        df.loc[df['RSI'] > 70, 'Signal'] = 0
        df['Signal'] = df['Signal'].ffill().fillna(0)
        
        df['Strategy_Ret'] = df['Signal'].shift(1) * df['Daily_Ret']
        
        mask = (df.index >= self.start) & (df.index <= self.end)
        df = df.loc[mask].copy()
        self.results['RSI'] = (1 + df['Strategy_Ret']).cumprod() - 1

    def load_trading_agents(self):
        """讀取 TradingAgents 的 Excel 績效"""
        if not os.path.exists(self.agent_path):
            print(f"⚠️ 找不到 TradingAgents 報告 ({self.agent_path})，將跳過此策略。")
            return

        try:
            df_agent = pd.read_excel(self.agent_path)
            if df_agent.empty: return

            df_agent['Date'] = pd.to_datetime(df_agent['Date'])
            
            # [防護] 去除重複日期，只保留最後一筆
            df_agent = df_agent.drop_duplicates(subset=['Date'], keep='last')
            
            df_agent = df_agent.set_index('Date')
            
            if 'Cumulative_Return_Pct' in df_agent.columns:
                agent_series = df_agent['Cumulative_Return_Pct'] / 100
            else:
                print("⚠️ Excel 中沒有累積報酬率數據。")
                return

            # 重新對齊到基準數據的日期
            aligned_series = agent_series.reindex(self.results.index, method='ffill').fillna(0)
            self.results['TradingAgents (Ours)'] = aligned_series
            
        except Exception as e:
            print(f"❌ 讀取 Excel 失敗: {e}")

    def calculate_metrics(self):
        """計算 Sharpe, MDD 等指標並印出"""
        if self.results.empty:
            print("⚠️ 無結果數據可計算指標。")
            return

        print(f"\n📊 [{self.ticker}] 策略績效評估:")
        print(f"{'Strategy':<20} {'Total Ret':<10} {'Ann. Ret':<10} {'Sharpe':<8} {'MDD':<8}")
        print("-" * 60)
        
        for col in self.results.columns:
            series = self.results[col]
            # 簡單防呆
            if series.empty: continue

            total_ret = series.iloc[-1]
            
            daily_rets = (1 + series) / (1 + series.shift(1)) - 1
            daily_rets = daily_rets.fillna(0)
            
            days = (series.index[-1] - series.index[0]).days
            ann_ret = (1 + total_ret) ** (365 / days) - 1 if days > 0 else 0
            
            std = daily_rets.std()
            sharpe = (daily_rets.mean() / std) * np.sqrt(252) if std != 0 else 0
            
            cum_max = (1 + series).cummax()
            drawdown = (1 + series) / cum_max - 1
            mdd = drawdown.min()
            
            print(f"{col:<20} {total_ret*100:>7.2f}% {ann_ret*100:>7.2f}% {sharpe:>8.2f} {mdd*100:>7.2f}%")

    def plot_comparison(self, auto_open=True):
        """繪圖 (支援自動開關視窗)"""
        if self.results.empty:
            print("⚠️ 無數據可繪圖。")
            return

        plt.figure(figsize=(12, 6))
        
        styles = {
            'Buy & Hold': {'color': 'gray', 'linestyle': '--', 'alpha': 0.6},
            'SMA': {'color': 'orange', 'alpha': 0.7},
            'MACD': {'color': 'purple', 'alpha': 0.7},
            'RSI': {'color': 'brown', 'alpha': 0.7},
            'TradingAgents (Ours)': {'color': 'green', 'linewidth': 2.5}
        }
        
        for col in self.results.columns:
            style = styles.get(col, {})
            plt.plot(self.results.index, self.results[col] * 100, label=col, **style)
            
        plt.title(f'Cumulative Return Comparison - {self.ticker}', fontsize=14)
        plt.ylabel('Cumulative Return (%)', fontsize=12)
        plt.xlabel('Date', fontsize=12)
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # 存檔
        save_path = f"results/{self.ticker}_benchmark_comparison.png"
        plt.savefig(save_path, dpi=300)
        print(f"📈 [{self.ticker}] 比較圖表已儲存至: {save_path}")
        
        if auto_open:
            print("👀 顯示圖表 (關閉視窗後繼續)...")
            plt.show()
        else:
            plt.close() # 關閉圖表釋放記憶體

if __name__ == "__main__":
    # 設定參數
    TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"] # ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA"]
    START_DATE = "2025-01-01"  
    END_DATE = "2025-12-31"

    print(f"🚀 開始批量執行基準比較，共 {len(TICKERS)} 檔")

    for TICKER in TICKERS:
        print(f"\n{'='*50}")
        print(f"🔄 正在處理: {TICKER}")
        print(f"{'='*50}")

        EXCEL_PATH = f"results/{TICKER}_backtest_results.xlsx"
        
        # 檢查檔案是否存在，不存在就跳過
        if not os.path.exists(EXCEL_PATH):
            print(f"⚠️ 跳過 {TICKER}: 找不到回測 Excel 檔案 ({EXCEL_PATH})")
            continue

        runner = BenchmarkRunner(TICKER, START_DATE, END_DATE, EXCEL_PATH)
        runner.fetch_data()
        
        if runner.data is None or runner.data.empty:
            print(f"⚠️ 跳過 {TICKER}: 無法獲取基準股價數據")
            continue
        
        # 計算各個基準
        runner.calc_buy_and_hold()
        runner.calc_sma_strategy()
        runner.calc_macd_strategy()
        runner.calc_rsi_strategy()
        
        # 載入我們 AI 的成績
        runner.load_trading_agents()
        
        # 輸出數據
        runner.calculate_metrics()
        
        # 繪圖
        # auto_open=True:  每畫完一張圖會彈出來，您關掉後才會跑下一張 (適合檢查)
        # auto_open=False: 不彈窗，直接存檔並跑下一張 (適合全自動)
        runner.plot_comparison(auto_open=True)

    print("\n🎉 所有基準比較圖表已產出完畢！")