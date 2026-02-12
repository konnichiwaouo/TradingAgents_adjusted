import time
import threading
from .alpha_vantage_common import _make_api_request, format_datetime_for_api

# ==========================================
# [新增] 全域鎖與計時器 (解決並發與速率限制問題)
# ==========================================
_api_lock = threading.Lock()
_last_request_time = 0

def smart_rate_limit(func):
    """
    智慧限流裝飾器：
    1. 使用 Lock 確保同一時間只有一個執行緒能發送請求 (解決並發問題)。
    2. 強制計算與上次請求的時間差，若不足 15 秒則強制等待 (解決 Alpha Vantage 免費版限制)。
    """
    def wrapper(*args, **kwargs):
        global _last_request_time
        
        # 1. 搶鎖：這一行會擋住所有同時想要執行的其他執行緒
        with _api_lock:
            current_time = time.time()
            elapsed_time = current_time - _last_request_time

            # 免費版建議間隔 2 秒以策安全
            wait_time = 2 - elapsed_time
            
            # 2. 如果距離上次請求太近，強制睡覺
            if wait_time > 0:
                print(f"⏳ [Alpha Vantage] 觸發冷卻，強制等待 {wait_time:.2f} 秒...")
                time.sleep(wait_time)
            
            try:
                # 3. 執行原本的函式 (這會去呼叫 _make_api_request)
                print(f"🚀 [Alpha Vantage] 執行請求: {func.__name__}")
                result = func(*args, **kwargs)
                return result
            finally:
                # 4. 更新最後請求時間
                _last_request_time = time.time()
                
    return wrapper
# ==========================================


# [修改] 加上裝飾器
@smart_rate_limit
def get_news(ticker, start_date, end_date) -> dict[str, str] | str:
    """Returns live and historical market news & sentiment data from premier news outlets worldwide.

    Covers stocks, cryptocurrencies, forex, and topics like fiscal policy, mergers & acquisitions, IPOs.

    Args:
        ticker: Stock symbol for news articles.
        start_date: Start date for news search.
        end_date: End date for news search.

    Returns:
        Dictionary containing news sentiment data or JSON string.
    """

    params = {
        "tickers": ticker,
        "time_from": format_datetime_for_api(start_date),
        "time_to": format_datetime_for_api(end_date),
        "sort": "LATEST",
        "limit": "50",
    }
    
    # 這裡會去呼叫 common 裡的發送函式，但因為被 wrapper 包住，所以會先排隊
    return _make_api_request("NEWS_SENTIMENT", params)


# [修改] 加上裝飾器 (Insider Transactions 也會消耗 API Quota，所以也要加)
@smart_rate_limit
def get_insider_transactions(symbol: str) -> dict[str, str] | str:
    """Returns latest and historical insider transactions by key stakeholders.

    Covers transactions by founders, executives, board members, etc.

    Args:
        symbol: Ticker symbol. Example: "IBM".

    Returns:
        Dictionary containing insider transaction data or JSON string.
    """

    params = {
        "symbol": symbol,
    }

    return _make_api_request("INSIDER_TRANSACTIONS", params)