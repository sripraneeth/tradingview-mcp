# 📈 TradingView MCP Server

A powerful Model Context Protocol (MCP) server that provides advanced cryptocurrency and stock market analysis using TradingView data. Perfect for traders, analysts, and AI assistants who need real-time market intelligence.

## 🎥 Demo Video

> **Quick 19-second demo showing the MCP server in action**
> 

https://github-production-user-asset-6210df.s3.amazonaws.com/67838093/478689497-4a605d98-43e8-49a6-8d3a-559315f6c01d.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAVCODYLSA53PQK4ZA%2F20250816%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250816T155717Z&X-Amz-Expires=300&X-Amz-Signature=1362a9ea0e886268315cfa5b63951c82929ea01c9d826c87060e3ac116cf9531&X-Amz-SignedHeaders=host

## ✨ Key Features

- 🚀 **Real-time Market Screening**: Find top gainers, losers, and trending stocks/crypto
- 📊 **Advanced Technical Analysis**: Bollinger Bands, RSI, MACD, and more indicators  
- 🎯 **Bollinger Band Intelligence**: Proprietary rating system (-3 to +3) for squeeze detection
- 🕯️ **Pattern Recognition**: Detect consecutive bullish/bearish candle formations
- 💎 **Multi-Market Support**: Crypto exchanges (KuCoin, Binance, Bybit) + Traditional markets (NASDAQ, BIST)
- 📰 **News Intelligence**: Market and ticker-level news sentiment (Finnhub-powered)
- ⏰ **Multi-Timeframe Analysis**: From 5-minute to monthly charts
- 🔍 **Individual Asset Deep-Dive**: Comprehensive technical analysis for any symbol

## 🚀 Quick Start

### Option 1: Claude Desktop (Recommended)

1. **Install UV Package Manager:**
   ```bash
   # macOS (Homebrew)
   brew install uv
   
   # Windows
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # macOS/Linux (Direct)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Add to Claude Desktop Configuration:**
   
   **Config Path:**
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   
   ```json
   {
     "mcpServers": {
       "tradingview-mcp": {
         "command": "uv",
         "args": [
           "tool", "run", "--from",
           "git+https://github.com/sripraneeth/tradingview-mcp.git",
           "tradingview-mcp"
         ]
       }
     }
   }
   ```

3. **Restart Claude Desktop** - The server will be automatically available!

📋 **For detailed Windows instructions, see [INSTALLATION.md](INSTALLATION.md)**

### Option 2: Manual Installation

```bash
# Clone the repository
git clone https://github.com/sripraneeth/tradingview-mcp.git
cd tradingview-mcp

# Install dependencies
uv sync

# For local development, add to Claude Desktop:
```

**Windows Configuration Path:**
`%APPDATA%\Claude\claude_desktop_config.json`

**macOS Configuration Path:**
`~/Library/Application Support/Claude/claude_desktop_config.json`

**Configuration for Local Setup:**
```json
{
  "mcpServers": {
    "tradingview-mcp-local": {
      "command": "C:\\path\\to\\your\\tradingview-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\your\\tradingview-mcp\\src\\tradingview_mcp\\server.py"],
      "cwd": "C:\\path\\to\\your\\tradingview-mcp"
    }
  }
}
```

**macOS/Linux Configuration:**
```json
{
  "mcpServers": {
    "tradingview-mcp-local": {
      "command": "uv",
      "args": ["run", "python", "src/tradingview_mcp/server.py"],
      "cwd": "/path/to/your/tradingview-mcp"
    }
  }
}
```

### Optional: Enable News Tools (Finnhub)

News tools require a Finnhub API key.

1. Create a free API key from [finnhub.io](https://finnhub.io/)
2. Set `FINNHUB_API_KEY` in your environment or MCP config

**Claude Desktop config example:**
```json
{
  "mcpServers": {
    "tradingview-mcp": {
      "command": "uv",
      "args": [
        "tool", "run", "--from",
        "git+https://github.com/sripraneeth/tradingview-mcp.git",
        "tradingview-mcp"
      ],
      "env": {
        "FINNHUB_API_KEY": "your_finnhub_api_key_here"
      }
    }
  }
}
```

If `FINNHUB_API_KEY` is missing, news tools return a structured configuration error.

## 🛠️ Available Tools

Tool naming now follows market-prefixed groups:

- `crypto_*`
- `stocks_*`
- `futures_*`
- `indices_*`
- `news_*`

> ✅ **Backward compatibility:** legacy unprefixed aliases (like `top_gainers`, `coin_analysis`, `bollinger_scan`) still work and map to the corresponding `crypto_*` tools.

### 💰 Crypto Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `crypto_top_gainers` | Find highest-performing crypto symbols | Top KuCoin gainers in 15m |
| `crypto_top_losers` | Find biggest crypto decliners | Biggest Binance losers today |
| `crypto_bollinger_scan` | Find low-BBW squeeze setups | Coins ready for breakout |
| `crypto_rating_filter` | Filter by Bollinger rating | Strong buy signals (+2) |
| `crypto_analysis` | Full technical analysis for one symbol | Analyze BTCUSDT on BYBIT |
| `crypto_consecutive_candles_scan` | Consecutive bullish/bearish candle scan | 3 bullish candles on KUCOIN |
| `crypto_advanced_candle_pattern` | Multi-timeframe candle structure scan | Progressive candle growth scan |
| `crypto_volume_breakout_scanner` | Volume + price breakout scanner | High-volume movers |
| `crypto_volume_confirmation_analysis` | Volume confirmation for one symbol | Validate BTC move with volume |
| `crypto_smart_volume_scanner` | Volume + RSI + move combined filter | Oversold high-volume opportunities |

### 📈 Stocks Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `stocks_top_gainers` | Top stock gainers | NASDAQ leaders in 15m |
| `stocks_top_losers` | Top stock losers | NYSE decliners today |
| `stocks_bollinger_scan` | Stock squeeze scanner | Low-BBW US equities |
| `stocks_analysis` | Full stock analysis | Analyze AAPL on NASDAQ |
| `stocks_volume_breakout` | Stock volume breakout scan | Volume-backed breakouts on TSX |
| `stocks_smart_scanner` | Volume + RSI stock scan | Oversold high-volume names |
| `stocks_levels` | Pivot/support/resistance levels | Key levels for SPY ETF |

### 📉 Futures Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `futures_analysis` | Full futures symbol analysis | Analyze ES1! on CME_MINI |
| `futures_top_gainers` | Top futures gainers | CME movers in 15m |
| `futures_top_losers` | Top futures losers | CBOT decliners |
| `futures_volume_breakout` | Futures volume-backed breakout scan | Strong volume moves on CME |
| `futures_levels` | Pivot/support/resistance levels | Levels for NQ1! |
| `futures_orb_predictor` | Opening range breakout levels | ORB for CL1! |

### 🌍 Indices Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `indices_analysis` | Full index analysis | Analyze SPX on CBOE |
| `indices_bollinger_scan` | Index squeeze scanner | Low-BBW indices |
| `indices_rating_filter` | Filter indices by rating | Rating +2 indices on CBOE |
| `indices_levels` | Pivot/support/resistance levels | Levels for VIX |

### 📰 News Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `news_market_sentiment` | Market/category news + sentiment summary | General market sentiment snapshot |
| `news_ticker_impact` | Ticker-specific news impact and sentiment | Impact check for AAPL |
| `news_breaking` | Latest breaking news + sentiment summary | Latest market headlines |

### 📋 Information
| Tool | Description |
|------|-------------|
| `exchanges://list` | List all supported exchanges and markets |

## 📝 Usage Examples

### Talk to Claude Like This:

**Basic Market Screening:**
```
"Show me the top 10 crypto gainers on KuCoin in the last 15 minutes"
"Find the biggest losers on Binance today"  
"Which Turkish stocks (BIST) are down more than 5% today?"
```

**Technical Analysis:**
```
"Analyze Bitcoin with all technical indicators"
"Find crypto coins with Bollinger Band squeeze (BBW < 0.05)"
"Show me coins with strong buy signals (rating +2)"
"Analyze IBM stock on NYSE with technical indicators"
```

**Stocks / ETFs / Futures / Indices:**
```
"Use stocks_top_gainers for NASDAQ in 15m"
"Analyze SPY ETF on AMEX using stocks_analysis"
"Run futures_analysis for ES1! on CME_MINI, timeframe 15m"
"Get indices_levels for SPX on CBOE"
"Find TSX stocks with low BBW using stocks_bollinger_scan"
```

**Pattern Recognition:**
```
"Find coins with 3 consecutive bullish candles on Bybit"
"Scan for stocks showing growing candle patterns"
"Which assets have tight Bollinger Bands ready for breakout?"
```

**News & Sentiment:**
```
"Use news_breaking with limit 10"
"Get news_market_sentiment for category general"
"Check news_ticker_impact for TSLA with limit 15"
```

**Advanced Queries:**
```
"Compare AAPL vs TSLA technical indicators"
"Find high-volume crypto with RSI below 30"
"Show me NASDAQ stocks with strong momentum"
"Find NYSE stocks with Bollinger Band squeeze"
```

## 🎯 Understanding the Bollinger Band Rating System

Our proprietary rating system helps identify trading opportunities:

| Rating | Signal | Description |
|--------|---------|-------------|
| **+3** | 🔥 Strong Buy | Price above upper Bollinger Band |
| **+2** | ✅ Buy | Price in upper 50% of bands |
| **+1** | ⬆️ Weak Buy | Price above middle line |
| **0** | ➡️ Neutral | Price at middle line |
| **-1** | ⬇️ Weak Sell | Price below middle line |
| **-2** | ❌ Sell | Price in lower 50% of bands |
| **-3** | 🔥 Strong Sell | Price below lower Bollinger Band |

**Bollinger Band Width (BBW)**: Lower values indicate tighter bands → potential breakout coming!

## 🏢 Supported Markets & Exchanges

| Market Type | Exchanges / Identifiers |
|-------------|--------------------------|
| Crypto | `KUCOIN`, `BINANCE`, `BYBIT`, `BITGET`, `OKX`, `COINBASE`, `GATEIO`, `HUOBI`, `BITFINEX`, `KRAKEN`, `BITSTAMP` |
| US Equities / ETFs | `NASDAQ`, `NYSE`, `AMEX` |
| Canada Equities | `TSX` |
| Europe / Turkey / APAC | `BIST`, `BURSA`, `MYX`, `KLSE`, `ACE`, `LEAP`, `HKEX`, `HK`, `HSI` |
| Futures / Derivatives | `CME_MINI`, `CME`, `CBOT`, `CBOE` |
| Index / Macro Feeds | `SP`, `TVC` |

Use `exchanges://list` to retrieve the currently available exchange universe in your runtime.

### ⏰ Supported Timeframes
`5m`, `15m`, `1h`, `4h`, `1D`, `1W`, `1M`

## 📊 Technical Indicators Included

- **Bollinger Bands** (20, 2) - Volatility and squeeze detection
- **RSI** (14) - Momentum oscillator  
- **Moving Averages** - SMA20, EMA50, EMA200
- **MACD** - Trend and momentum
- **ADX** - Trend strength measurement
- **Stochastic** - Overbought/oversold conditions
- **Volume Analysis** - Market participation
- **Price Action** - OHLC data with percentage changes

## 🚨 Troubleshooting

### Common Issues:

**1. "No data found" errors:**
- Try different exchanges (KuCoin usually works best)
- Use standard timeframes (15m, 1h, 1D)
- Check symbol format (e.g., "BTCUSDT" not "BTC")

**2. Empty arrays or rate limiting:**
- If you get empty results, you may have hit TradingView's rate limits
- Wait 5-10 minutes between query sessions
- The server automatically handles retries
- KuCoin and BIST have the most reliable data

**3. Claude Desktop not detecting the server:**
- Restart Claude Desktop after adding configuration
- Check that UV is installed: `uv --version`
- Verify the configuration JSON syntax

**4. Slow responses:**
- First request may be slower (warming up)
- Subsequent requests are much faster
- Consider using smaller limits (5-10 items)

## 🔧 Development & Customization

### Running in Development Mode:
```bash
# Clone and setup
git clone https://github.com/sripraneeth/tradingview-mcp.git
cd tradingview-mcp
uv sync

# Run with MCP Inspector for debugging
uv run mcp dev src/tradingview_mcp/server.py

# Test individual functions
uv run python test_api.py
```

### Adding New Exchanges:
The server is designed to be easily extensible. Check `src/tradingview_mcp/core/` for the modular architecture.

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Ideas for Contributions:
- Add new exchanges or markets
- Implement additional technical indicators  
- Improve error handling and rate limiting
- Add more candlestick pattern recognition
- Create comprehensive test suite

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🐛 Support & Issues

- **Report bugs**: [GitHub Issues](https://github.com/sripraneeth/tradingview-mcp/issues)
- **Feature requests**: Open an issue with the "enhancement" label
- **Questions**: Check existing issues or open a new discussion

## 🌟 Star This Project

If you find this MCP server useful, please ⭐ star the repository to help others discover it!

---

**Built with ❤️ for traders and AI enthusiasts**

*Empowering intelligent trading decisions through advanced market analysis*
