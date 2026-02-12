import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta
from pathlib import Path
from cli.models import AnalystType
# [重要] 匯入剛剛新增的 parse_signal_from_content
from cli.main import run_analysis_execution, parse_signal_from_content
from trade_manager import TradeManager

# ================= 設定區 =================
TICKERS = ["AMZN", "TSLA"] # mega 7: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA"]
START_DATE = "2025-01-01"
END_DATE = "2025-12-31"

AZURE_CONFIG = {
    "llm_provider": "azure",
    "backend_url": "https://cmoneyfund.openai.azure.com/", 
    "shallow_thinker": "gpt-4o-mini", 
    "deep_thinker": "gpt-4o",         
    "research_depth": 3,
}
# =========================================

def get_market_data(ticker, start, end):
    """下載完整的歷史數據以便查詢 T+1 開盤價"""
    print(f"📥 下載 {ticker} 股價數據中...")
    try:
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        extended_end_dt = end_dt + timedelta(days=10)
        extended_end_str = extended_end_dt.strftime("%Y-%m-%d")
        
        df = yf.download(ticker, start=start, end=extended_end_str, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"❌ 下載數據失敗: {e}")
        return pd.DataFrame()

def main():
    print(f"🚀 開始執行全自動回測與記帳系統")
    
    for ticker in TICKERS:
        # 1. 初始化帳務管理器 (會自動讀取舊的 Excel 狀態)
        trader = TradeManager(ticker, initial_capital=100000)
        
        # 2. 獲取市場數據
        market_data = get_market_data(ticker, START_DATE, END_DATE)
        if market_data.empty: continue
            
        trading_days = market_data.index.strftime('%Y-%m-%d').tolist()
        target_days = [d for d in trading_days if START_DATE <= d <= END_DATE]
        
        print(f"🔵 {ticker}: 共有 {len(target_days)} 個交易日需模擬")

        for idx, analysis_date in enumerate(target_days):
            # 檢查 Excel 是否已經有「這個日期」的紀錄 (若有則完全跳過)
            # 注意: 我們 Excel 紀錄的是 T+1 交易日，但這裡簡單起見，如果已經跑過就不重複
            # 若您希望強制重新整理 Excel，可以把這行註解掉
            # if any(r['Date'] == analysis_date for r in trader.records): continue

            print(f"\n[{ticker}] 分析日: {analysis_date} ({idx+1}/{len(target_days)})")
            
            # 3. 準備 T+1 數據
            try:
                ts_analysis_date = pd.Timestamp(analysis_date)
                if ts_analysis_date not in market_data.index: continue
                    
                current_loc = market_data.index.get_loc(ts_analysis_date)
                next_loc = current_loc + 1
                if next_loc >= len(market_data):
                    print("⚠️ 已達數據末端，結束。")
                    break
                
                next_date = market_data.index[next_loc]
                next_date_str = next_date.strftime('%Y-%m-%d')
                try:
                    next_open = float(market_data.iloc[next_loc]['Close'])
                except KeyError:
                    next_open = float(market_data.iloc[next_loc]['close'])
                
            except Exception as e:
                print(f"❌ 數據錯誤: {e}")
                continue

            # 4. 判斷訊號來源 (讀檔 vs 跑AI)
            signal = "HOLD"
            
            # 檢查最終決策報告是否存在
            report_path = Path("results") / ticker / analysis_date / "reports" / "final_trade_decision.md"
            
            if report_path.exists():
                print(f"📂 發現現有報告，正在讀取: {report_path}")
                try:
                    with open(report_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # [關鍵] 使用共用的解析邏輯
                    signal = parse_signal_from_content(content)
                    print(f"🔍 [Read File] 從檔案解析訊號: {signal}")
                    
                except Exception as e:
                    print(f"⚠️ 讀取報告失敗 ({e})，將重新執行 AI 分析...")
                    report_path = None # 強制設為不存在，觸發下方 AI 邏輯

            # 如果報告不存在 (或讀取失敗)，則跑 AI
            if not report_path.exists():
                print("🤖 報告不存在，啟動 AI 分析...")
                selections = {
                    "ticker": ticker,
                    "analysis_date": analysis_date,
                    "analysts": [AnalystType.MARKET, AnalystType.SOCIAL, AnalystType.NEWS, AnalystType.FUNDAMENTALS],
                    **AZURE_CONFIG
                }
                try:
                    signal = run_analysis_execution(selections)
                    print(f"🤖 [AI Run] AI 決策: {signal}")
                except Exception as e:
                    print(f"❌ AI 執行失敗: {e}")
                    signal = "HOLD"

            # 5. 執行記帳 (無論訊號是讀來的還是算出來的，都要記)
            try:
                record = trader.execute_trade(
                    date=next_date_str, 
                    signal=signal, 
                    open_price=next_open
                )
                print(f"💰 帳務更新: {next_date_str} | 動作: {record['Action']} | 資產: {int(record['Total_Value'])}")
            except Exception as e:
                print(f"❌ 記帳失敗: {e}")

if __name__ == "__main__":
    main()