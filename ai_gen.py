import alpaca_trade_api as tradeapi
import requests
import time
import pandas as pd
from alpaca_trade_api.rest import TimeFrame
import datetime
from pytz import timezone
from alpaca_trade_api.rest import APIError
import os
from dotenv import load_dotenv

# Load and validate credentials
load_dotenv()
API_KEY = 'your api key'
API_SECRET = 'your api secret'
BASE_URL = 'your url'

if not all([API_KEY, API_SECRET, BASE_URL]):
    raise ValueError("Missing required environment variables")


# Initialize API with rate limiting
api = tradeapi.REST(
    API_KEY, 
    API_SECRET, 
    BASE_URL, 
    api_version='v2',
    rate_limit=True
)

# Trading parameters
STOCK_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "FB", "TSLA", "BRK.B", "V", "JNJ", "WMT", 
                "JPM", "MA", "PG", "UNH", "NVDA", "HD", "DIS", "PYPL", "VZ", "ADBE", 
                "NFLX", "INTC", "CMCSA", "PFE", "KO", "PEP", "MRK", "T", "ABT", "CSCO", 
                "XOM", "NKE", "LLY", "CVX", "ORCL", "MCD", "DHR", "MDT", "WFC", "BMY", 
                "COST", "NEE", "ACN", "AVGO", "TXN", "HON", "PM", "UNP", "QCOM"]

# Risk management configuration
RISK_CONFIG = {
    'stop_loss_percentage': 0.05,
    'take_profit_percentage': 0.1,
    'rsi_period': 14
}

def marketValue(stock_symbol):
    latest_trade = api.get_latest_trade(stock_symbol)
    current_price = latest_trade.price
    print(f"The current market value of {stock_symbol} is: ${current_price:.2f}")
    return current_price

def buyStock(stock_symbol):
    url = BASE_URL
    payload = {
        "symbol": stock_symbol,              
        "qty": 1,                    
        "side": "buy",                
        "type": "market",              
        "time_in_force": "day"          
    }
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
        "accept": "application/json",
        "content-type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    print(response.text)

def sellStock(stock_symbol):
    url = BASE_URL
    payload = {
        "symbol": stock_symbol,           
        "qty": 1,                     
        "side": "sell",            
        "type": "market",             
        "time_in_force": "day"         
    }
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
        "accept": "application/json",
        "content-type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    print(response.text)

def buyPrice(stock_symbol): 
    position = api.get_position(stock_symbol)
    average_buy_price = position.avg_entry_price
    print(f"You bought {stock_symbol} at an average price of: ${average_buy_price}")
    return average_buy_price

def checkHave(api, stock_symbol):
    """
    Checks if the user holds a position for the given stock symbol.

    Args:
    api (alpaca_trade_api.REST): The Alpaca API client instance.
    stock_symbol (str): The stock symbol to check, e.g., 'AAPL'.

    Returns:
    bool: True if the position exists, False otherwise.
    """
    try:
        position = api.get_position(stock_symbol)
        print(f"Current position for {stock_symbol}: {position}")
        return True
    except APIError as e:
        # Specifically catch APIError from Alpaca indicating the position does not exist
        if "position does not exist" in str(e):
            print(f"No position exists for {stock_symbol}. Returning False.")
            return False
        else:
            raise e  # Re-raise any other API errors

# RSI Calculation Function
def calculate_rsi(prices, period=14):
    """
    Args:
        prices (list or pandas.Series): A list or series of closing prices.
        period (int): The number of periods to use for RSI calculation. Default is 14.

    Returns:
        float: The RSI value.
    """
    # Ensure we have enough data points
    if len(prices) < period + 1:  # Need period + 1 prices for calculation
        raise ValueError(f"Not enough data points to calculate RSI. Required: {period + 1}, Given: {len(prices)}")

    # Convert prices to a pandas Series if it isn't already
    if not isinstance(prices, pd.Series):
        prices = pd.Series(prices)

    # Calculate price changes
    delta = prices.diff()
    
    # Separate gains and losses
    gains = delta.where(delta > 0, 0)  # Keep positive changes, else 0
    losses = -delta.where(delta < 0, 0)  # Keep negative changes, else 0

    # Calculate average gain and loss over the period
    avg_gain = gains.rolling(window=period, min_periods=1).mean()
    avg_loss = losses.rolling(window=period, min_periods=1).mean()

    # Calculate the RS (Relative Strength)
    rs = avg_gain / avg_loss

    # Calculate the RSI
    rsi = 100 - (100 / (1 + rs))

    # Return the latest RSI value
    return rsi.iloc[-1]


def get_historical_prices(stock_symbol, timeframe='minute', limit=100):
    """
    Fetch historical prices for a given stock symbol using Alpaca's `get_bars` method.

    Args:
    stock_symbol (str): The stock symbol to get historical data for.
    timeframe (str): The timeframe for the bars ('day' or 'minute'). Default is 'minute'.
    limit (int): The number of historical data points to fetch. Default is 100.

    Returns:
    list: A list of closing prices for the specified stock.
    """
    # Convert the timeframe string to Alpaca's TimeFrame format
    if timeframe == 'day':
        alpaca_timeframe = TimeFrame.Day
    elif timeframe == 'minute':
        alpaca_timeframe = TimeFrame.Minute
    else:
        raise ValueError("Invalid timeframe. Use 'day' or 'minute'.")

    # Fetch historical data using `get_bars`
    bars = api.get_bars(stock_symbol, alpaca_timeframe, limit=limit)

    # Check if the bars are returned and print out the length for debugging
    if len(bars) == 0:
        print(f"No historical data returned for {stock_symbol}.")
        return []

    print(f"Number of bars returned: {len(bars)}")

    # Extract closing prices from the returned bar data
    closing_prices = [bar.c for bar in bars]

    # Print the closing prices to check the data
    print(f"Closing prices for {stock_symbol}: {closing_prices}")

    return closing_prices

# Trading Strategy Function with Debugging
def trading_strategy(api, stock_symbol):
    """Execute trading strategy with improved risk management"""
    try:
        # Get current position and market value
        position = None
        try:
            position = api.get_position(stock_symbol)
        except APIError as e:
            if "position does not exist" not in str(e):
                raise e

        current_price = float(marketValue(stock_symbol))

        # Add position size limits
        max_position_size = 1000  # dollars
        current_value = float(position.qty) * current_price if position else 0

        if current_value > max_position_size:
            logging.warning(f"Position size ({current_value}) exceeds limit")
            return

        # Fetch historical prices and calculate RSI
        prices = get_historical_prices(stock_symbol, timeframe='minute', limit=100)
        rsi = calculate_rsi(prices, period=rsi_period)

        # Trading logic based on RSI
        if rsi < 30:
            # Buy if RSI is below 30 (oversold)
            buyStock(stock_symbol)
        elif rsi > 70 and position:
            # Sell if RSI is above 70 (overbought) and we have a position
            sellStock(stock_symbol)

    except Exception as e:
        

def is_trading_hours(now=None):
    """Check if current time is during trading hours (9:30 AM - 4:00 PM EST, weekdays only)"""
    
    # Get current time in EST if not provided
    if now is None:
        est = timezone('EST')
        now = datetime.datetime.now(est)
    
    # Check if weekend
    if now.strftime('%A').lower() in ['saturday', 'sunday']:
        return False
        
    # Convert to time object for comparison
    current_time = now.time()
    market_open = datetime.time(9, 30, 0)
    market_close = datetime.time(16, 0, 0)
    
    # Check if within trading hours
    return market_open <= current_time <= market_close

# Example: Run the trading strategy for the top 50 stocks
def main():
    while True:
        try:
            est = timezone('EST')
            now = datetime.datetime.now(est)
            
            if not is_trading_hours(now):
                time.sleep(60)
                continue
            
            for stock_symbol in top_50_stocks:
                trading_strategy(api, stock_symbol)
                
        except Exception as e:
            logging.error(f"Error occurred: {str(e)}")
            time.sleep(60)

if __name__ == "__main__":
    main()
