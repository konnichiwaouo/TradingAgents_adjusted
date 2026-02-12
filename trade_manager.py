import pandas as pd
import os

class TradeManager:
    def __init__(self, ticker, initial_capital=100000):
        self.ticker = ticker
        self.capital = initial_capital  # 現金
        self.shares = 0                 # 持股數量
        self.initial_capital = initial_capital
        self.records = []               # 交易紀錄
        self.file_path = f"results/{ticker}_backtest_results.xlsx"

        # 如果檔案存在，載入上次的狀態 (支援中斷續跑)
        if os.path.exists(self.file_path):
            self.load_state()

    def load_state(self):
        """從 Excel 讀取最後的狀態"""
        try:
            df = pd.read_excel(self.file_path)
            if not df.empty:
                last_row = df.iloc[-1]
                self.capital = last_row['Cash']
                self.shares = last_row['Shares']
                # 重新載入歷史紀錄
                self.records = df.to_dict('records')
                print(f"📖 已載入 {self.ticker} 歷史帳務，目前現金: {self.capital}, 持股: {self.shares}")
        except Exception as e:
            print(f"⚠️ 讀取歷史檔失敗，將重新開始: {e}")

    def execute_trade(self, date, signal, open_price):
        """
        執行交易邏輯 (全倉進出)
        date: T+1 日期 (實際交易日)
        signal: BUY / SELL / HOLD
        open_price: T+1 開盤價
        """
        action = "HOLD"
        trade_pnl = 0
        shares_delta = 0
        amount = 0

        # 1. 買入邏輯 (有錢且訊號是 Buy)
        if signal == "BUY" and self.capital > 0:
            # 全倉買入 (計算能買幾股)
            # 預留 1% 現金避免滑價或手續費導致透支
            available_cash = self.capital * 1 
            buy_shares = int(available_cash / open_price)
            
            if buy_shares > 0:
                cost = buy_shares * open_price
                self.capital -= cost
                self.shares += buy_shares
                action = "BUY"
                shares_delta = buy_shares
                amount = cost

        # 2. 賣出邏輯 (有股且訊號是 Sell)
        elif signal == "SELL" and self.shares > 0:
            revenue = self.shares * open_price
            
            # 計算這筆交易的平倉損益 (這裡簡化計算，用總資產變化來看)
            # 若要精確計算每一筆 trade PnL 需要 FIFO 佇列，這裡先算總資產
            
            self.capital += revenue
            action = "SELL"
            shares_delta = -self.shares
            amount = revenue
            self.shares = 0

        # 3. 計算當下總資產價值
        total_value = self.capital + (self.shares * open_price)
        total_return = (total_value - self.initial_capital) / self.initial_capital * 100

        # 4. 記錄
        record = {
            "Date": date,
            "Ticker": self.ticker,
            "Signal": signal,      # AI 給的建議
            "Action": action,      # 實際執行的動作
            "Open_Price": open_price,
            "Shares_Delta": shares_delta,
            "Transaction_Amount": amount,
            "Cash": self.capital,
            "Shares": self.shares,
            "Total_Value": total_value,
            "Cumulative_Return_Pct": round(total_return, 2)
        }
        self.records.append(record)
        self.save_to_excel()
        
        return record

    def save_to_excel(self):
        """即時存檔"""
        df = pd.DataFrame(self.records)
        # 確保目錄存在
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        df.to_excel(self.file_path, index=False)