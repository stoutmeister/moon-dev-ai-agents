"""
🌙 Moon Dev's Short Agent 🐻
A bot that hunts for high-probability SHORT setups on Hyperliquid perps.

How it works:
1. Pulls REAL OHLCV + funding data from Hyperliquid for each monitored symbol
2. Scores the bearish setup 0-100 across 6 signals:
   - Downtrend structure (price < SMA20 < SMA50)
   - RSI overbought rollover (shorting strength, not weakness)
   - MACD bearish momentum
   - Bollinger upper band rejection
   - Bearish volume expansion
   - Crowded longs via high positive funding (squeeze fuel + you get paid to short)
3. If the score clears the threshold, the AI (via ModelFactory) gets the final say
4. Opens PAPER shorts with leverage, stop-loss and take-profit, and manages
   them every cycle (stop / target / AI COVER signal)

All positions are PAPER TRADES tracked in src/data/short_agent/ — this repo has
no live perp execution. Educational project, substantial risk of loss if you
wire this to real money. Moon Dev always prioritizes risk management! 🛡️
"""

# ============================================================================
# CONFIGURATION - EDIT THESE SETTINGS
# ============================================================================

# AI Model (via Model Factory) - 'groq', 'openai', 'claude', 'deepseek', 'xai', 'ollama'
AI_MODEL_TYPE = 'claude'
AI_MODEL_NAME = None  # None = default model for the type

# Symbols to hunt for shorts (Hyperliquid perp names)
SYMBOLS = ['BTC', 'ETH', 'SOL', 'DOGE', 'WIF']

# Data settings
TIMEFRAME = '15m'
BARS = 200

# Signal settings
SHORT_SCORE_THRESHOLD = 60   # Minimum bearish score (0-100) before asking the AI
AI_CONFIDENCE_THRESHOLD = 70 # Minimum AI confidence % to actually open the short

# Paper trading settings
USD_PER_SHORT = 100          # Notional collateral per short (USD)
LEVERAGE = 3                 # Paper leverage multiplier
STOP_LOSS_PCT = 2.0          # % price move AGAINST us (up) that stops us out
TAKE_PROFIT_PCT = 4.0        # % price move in our favor (down) that takes profit
MAX_OPEN_SHORTS = 3          # Max simultaneous open paper shorts

# Loop settings
SLEEP_BETWEEN_RUNS_MINUTES = 15

# ============================================================================
# END CONFIGURATION
# ============================================================================

SHORT_PROMPT = """
You are Moon Dev's AI Short Seller 🐻🌙

You ONLY evaluate SHORT opportunities. Analyze the bearish signal breakdown and
recent market data below and decide if this is a high-probability short.

Great shorts have:
1. Broken trend structure (lower highs, price under key MAs)
2. Momentum rolling over from overbought — short strength, never chase weakness
3. Crowded longs (high positive funding) that can fuel a long squeeze down
4. Clear invalidation (a stop level close by)

Dangerous shorts have:
1. Deeply oversold conditions (bounce risk)
2. Strong uptrends (never short a rocket just because it's up a lot)
3. Negative funding (crowd is already short - squeeze risk is UP, not down)

Respond in this exact format:
1. First line must be exactly one of: SHORT, COVER, or NOTHING (in caps)
2. Then your reasoning, and include a line like "Confidence: 75%"

Remember: the best short sellers pass on 90% of setups. Capital preservation
first — Moon Dev always prioritizes risk management! 🛡️
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from termcolor import cprint
from dotenv import load_dotenv

# Add project root to path for imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from src import nice_funcs_hl as hl
from src.models.model_factory import model_factory
from src.config import AI_TEMPERATURE, AI_MAX_TOKENS

load_dotenv()

# Data directory for this agent
DATA_DIR = Path(project_root) / 'src' / 'data' / 'short_agent'
POSITIONS_FILE = DATA_DIR / 'paper_positions.csv'
SIGNALS_FILE = DATA_DIR / 'signal_history.csv'

POSITION_COLUMNS = [
    'id', 'symbol', 'entry_time', 'entry_price', 'collateral_usd', 'leverage',
    'notional_usd', 'stop_loss', 'take_profit', 'status', 'exit_time',
    'exit_price', 'pnl_usd', 'pnl_pct', 'exit_reason', 'ai_confidence'
]


class ShortAgent:
    """🐻 Moon Dev's Short Agent - finds and paper-trades short setups"""

    def __init__(self):
        cprint(f"\n🐻 Initializing Short Agent with {AI_MODEL_TYPE} model...", "cyan")
        self.model = model_factory.get_model(AI_MODEL_TYPE, AI_MODEL_NAME)

        if not self.model:
            cprint(f"❌ Failed to initialize {AI_MODEL_TYPE} model!", "red")
            cprint("Available models:", "yellow")
            for model_type in model_factory._models.keys():
                cprint(f"  - {model_type}", "yellow")
            sys.exit(1)

        cprint(f"✅ Using model: {self.model.model_name}", "green")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.positions = self._load_positions()
        open_count = len(self.positions[self.positions['status'] == 'OPEN'])
        cprint(f"📂 Loaded {len(self.positions)} paper positions ({open_count} open)", "cyan")
        cprint("🐻 Moon Dev's Short Agent initialized! Time to hunt... 🌙", "green")

    # ------------------------------------------------------------------
    # Position storage
    # ------------------------------------------------------------------
    def _load_positions(self):
        if POSITIONS_FILE.exists():
            df = pd.read_csv(POSITIONS_FILE)
            for col in POSITION_COLUMNS:
                if col not in df.columns:
                    df[col] = None
            return df[POSITION_COLUMNS]
        return pd.DataFrame(columns=POSITION_COLUMNS)

    def _save_positions(self):
        self.positions.to_csv(POSITIONS_FILE, index=False)

    def _log_signal(self, symbol, score, breakdown, ai_action, ai_confidence, price):
        row = {
            'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'price': price,
            'short_score': score,
            'breakdown': json.dumps(breakdown),
            'ai_action': ai_action,
            'ai_confidence': ai_confidence,
        }
        df = pd.DataFrame([row])
        header = not SIGNALS_FILE.exists()
        df.to_csv(SIGNALS_FILE, mode='a', header=header, index=False)

    # ------------------------------------------------------------------
    # Signal engine
    # ------------------------------------------------------------------
    def score_short_setup(self, df, funding):
        """Score how juicy this short setup is, 0-100. Higher = more bearish."""
        last = df.iloc[-1]
        prev = df.iloc[-2]
        breakdown = {}

        # 1. Trend structure broken: price < SMA20 < SMA50 (20 pts)
        pts = 0
        if last['close'] < last['sma_20'] and last['sma_20'] < last['sma_50']:
            pts = 20
        elif last['close'] < last['sma_20']:
            pts = 10
        breakdown['trend_down'] = pts

        # 2. RSI rollover from overbought - short strength (15 pts)
        pts = 0
        recent_rsi_high = df['rsi'].tail(8).max()
        if recent_rsi_high > 65 and last['rsi'] < prev['rsi']:
            pts = 15
        elif last['rsi'] > 55 and last['rsi'] < prev['rsi']:
            pts = 7
        breakdown['rsi_rollover'] = pts

        # 3. MACD bearish momentum (20 pts)
        pts = 0
        macd_line = last.get('MACD_12_26_9')
        macd_signal = last.get('MACDs_12_26_9')
        macd_hist = last.get('MACDh_12_26_9')
        prev_hist = prev.get('MACDh_12_26_9')
        if pd.notna(macd_line) and pd.notna(macd_signal):
            if macd_line < macd_signal:
                pts = 12
                if pd.notna(macd_hist) and pd.notna(prev_hist) and macd_hist < prev_hist:
                    pts = 20  # bearish AND accelerating
        breakdown['macd_bearish'] = pts

        # 4. Bollinger upper band rejection (15 pts)
        pts = 0
        upper = last.get('BBU_5_2.0')
        mid = last.get('BBM_5_2.0')
        if pd.notna(upper) and pd.notna(mid):
            touched_upper = (df['high'].tail(5) >= df['BBU_5_2.0'].tail(5)).any()
            if touched_upper and last['close'] < mid:
                pts = 15
            elif touched_upper and last['close'] < upper:
                pts = 8
        breakdown['bb_rejection'] = pts

        # 5. Bearish volume expansion - red candles on heavy volume (10 pts)
        pts = 0
        avg_vol = df['volume'].tail(20).mean()
        is_red = last['close'] < last['open']
        if is_red and avg_vol > 0 and last['volume'] > 1.5 * avg_vol:
            pts = 10
        elif is_red and avg_vol > 0 and last['volume'] > avg_vol:
            pts = 5
        breakdown['bearish_volume'] = pts

        # 6. Crowded longs: high positive funding = squeeze fuel + paid to short (20 pts)
        pts = 0
        if funding:
            hourly_funding_pct = funding['funding_rate'] * 100
            annualized = hourly_funding_pct * 24 * 365
            breakdown['funding_annualized_pct'] = round(annualized, 2)
            if annualized > 30:
                pts = 20
            elif annualized > 15:
                pts = 12
            elif annualized > 0:
                pts = 5
        breakdown['crowded_longs'] = pts

        score = sum(v for k, v in breakdown.items() if k != 'funding_annualized_pct')
        return score, breakdown

    def build_market_summary(self, symbol, df, funding, score, breakdown):
        """Compact market snapshot for the AI - recent candles + indicators"""
        recent = df.tail(10)[['timestamp', 'open', 'high', 'low', 'close', 'volume',
                              'sma_20', 'sma_50', 'rsi']].round(4)
        last = df.iloc[-1]
        funding_line = "unavailable"
        if funding:
            funding_line = (f"hourly rate {funding['funding_rate'] * 100:.5f}% "
                            f"(~{funding['funding_rate'] * 100 * 24 * 365:.1f}% annualized), "
                            f"open interest {funding['open_interest']:,.0f}")
        return f"""Symbol: {symbol} (Hyperliquid perp, {TIMEFRAME} candles)
Current price: {last['close']}
Bearish score: {score}/100
Signal breakdown: {json.dumps(breakdown)}
Funding: {funding_line}

Last 10 candles with indicators:
{recent.to_string(index=False)}

Proposed paper trade if SHORT:
- Entry ~{last['close']}
- Stop loss: +{STOP_LOSS_PCT}% ({last['close'] * (1 + STOP_LOSS_PCT / 100):.4f})
- Take profit: -{TAKE_PROFIT_PCT}% ({last['close'] * (1 - TAKE_PROFIT_PCT / 100):.4f})
- Leverage: {LEVERAGE}x on ${USD_PER_SHORT} collateral
"""

    # ------------------------------------------------------------------
    # AI confirmation
    # ------------------------------------------------------------------
    def ask_ai(self, market_summary):
        """Get the AI's verdict: (action, confidence, reasoning)"""
        response = self.model.generate_response(
            system_prompt=SHORT_PROMPT,
            user_content=market_summary,
            temperature=AI_TEMPERATURE,
            max_tokens=AI_MAX_TOKENS
        )
        if hasattr(response, 'content'):
            response = response.content
        response = str(response)

        lines = [l.strip() for l in response.split('\n') if l.strip()]
        action = 'NOTHING'
        for candidate in ('SHORT', 'COVER', 'NOTHING'):
            if lines and candidate in lines[0].upper():
                action = candidate
                break

        confidence = 0
        for line in lines:
            if 'confidence' in line.lower():
                digits = ''.join(filter(str.isdigit, line))
                if digits:
                    confidence = min(int(digits), 100)
                break

        reasoning = '\n'.join(lines[1:]) if len(lines) > 1 else 'No reasoning provided'
        return action, confidence, reasoning

    # ------------------------------------------------------------------
    # Paper trading engine
    # ------------------------------------------------------------------
    def open_symbols(self):
        open_pos = self.positions[self.positions['status'] == 'OPEN']
        return set(open_pos['symbol'].tolist())

    def open_paper_short(self, symbol, price, confidence):
        position_id = f"{symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        stop = price * (1 + STOP_LOSS_PCT / 100)
        target = price * (1 - TAKE_PROFIT_PCT / 100)
        row = {
            'id': position_id,
            'symbol': symbol,
            'entry_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'entry_price': price,
            'collateral_usd': USD_PER_SHORT,
            'leverage': LEVERAGE,
            'notional_usd': USD_PER_SHORT * LEVERAGE,
            'stop_loss': stop,
            'take_profit': target,
            'status': 'OPEN',
            'exit_time': None,
            'exit_price': None,
            'pnl_usd': None,
            'pnl_pct': None,
            'exit_reason': None,
            'ai_confidence': confidence,
        }
        self.positions = pd.concat([self.positions, pd.DataFrame([row])], ignore_index=True)
        self._save_positions()
        cprint(f"\n🐻 PAPER SHORT OPENED: {symbol} @ {price}", "white", "on_red")
        cprint(f"   💰 ${USD_PER_SHORT} x {LEVERAGE}x = ${USD_PER_SHORT * LEVERAGE} notional", "yellow")
        cprint(f"   🛑 Stop: {stop:.4f} (+{STOP_LOSS_PCT}%) | 🎯 Target: {target:.4f} (-{TAKE_PROFIT_PCT}%)", "yellow")

    def close_paper_short(self, idx, exit_price, reason):
        pos = self.positions.loc[idx]
        entry = float(pos['entry_price'])
        # Short PnL: profit when price drops
        price_move_pct = (entry - exit_price) / entry * 100
        pnl_pct = price_move_pct * float(pos['leverage'])
        pnl_usd = float(pos['collateral_usd']) * pnl_pct / 100

        self.positions.loc[idx, 'status'] = 'CLOSED'
        self.positions.loc[idx, 'exit_time'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        self.positions.loc[idx, 'exit_price'] = exit_price
        self.positions.loc[idx, 'pnl_usd'] = round(pnl_usd, 2)
        self.positions.loc[idx, 'pnl_pct'] = round(pnl_pct, 2)
        self.positions.loc[idx, 'exit_reason'] = reason
        self._save_positions()

        color = "on_green" if pnl_usd >= 0 else "on_red"
        emoji = "💰" if pnl_usd >= 0 else "💸"
        cprint(f"\n{emoji} PAPER SHORT CLOSED: {pos['symbol']} @ {exit_price} ({reason})", "white", color)
        cprint(f"   Entry: {entry} → Exit: {exit_price} | PnL: ${pnl_usd:+.2f} ({pnl_pct:+.2f}% on collateral)", "cyan")

    def manage_open_positions(self, latest_prices, cover_signals):
        """Check stops/targets/AI cover signals on all open paper shorts"""
        open_pos = self.positions[self.positions['status'] == 'OPEN']
        if open_pos.empty:
            return

        cprint(f"\n🔎 Managing {len(open_pos)} open paper short(s)...", "cyan")
        for idx, pos in open_pos.iterrows():
            symbol = pos['symbol']
            price = latest_prices.get(symbol)
            if price is None:
                cprint(f"⚠️ No price for {symbol}, skipping management this cycle", "yellow")
                continue

            entry = float(pos['entry_price'])
            unrealized_pct = (entry - price) / entry * 100 * float(pos['leverage'])
            cprint(f"   {symbol}: entry {entry} | now {price} | unrealized {unrealized_pct:+.2f}%", "cyan")

            if price >= float(pos['stop_loss']):
                self.close_paper_short(idx, price, 'STOP_LOSS')
            elif price <= float(pos['take_profit']):
                self.close_paper_short(idx, price, 'TAKE_PROFIT')
            elif symbol in cover_signals:
                self.close_paper_short(idx, price, 'AI_COVER')

    def print_performance(self):
        """Print the paper trading scoreboard 📊"""
        closed = self.positions[self.positions['status'] == 'CLOSED']
        open_pos = self.positions[self.positions['status'] == 'OPEN']
        cprint("\n📊 Moon Dev's Short Agent Scoreboard", "white", "on_blue")
        if closed.empty:
            cprint("   No closed trades yet - the hunt continues... 🐻", "cyan")
        else:
            pnl = closed['pnl_usd'].astype(float)
            wins = (pnl > 0).sum()
            cprint(f"   Closed trades: {len(closed)} | Wins: {wins} | "
                   f"Win rate: {wins / len(closed) * 100:.0f}%", "cyan")
            cprint(f"   Total PnL: ${pnl.sum():+.2f} | Best: ${pnl.max():+.2f} | "
                   f"Worst: ${pnl.min():+.2f}", "cyan")
        cprint(f"   Open shorts: {len(open_pos)}/{MAX_OPEN_SHORTS}", "cyan")

    # ------------------------------------------------------------------
    # Main cycle
    # ------------------------------------------------------------------
    def run(self):
        """Run one full short-hunting cycle (BaseAgent-style interface)"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cprint(f"\n{'=' * 60}", "cyan")
        cprint(f"🐻 Short Agent cycle starting at {current_time}", "white", "on_blue")
        cprint(f"{'=' * 60}", "cyan")

        latest_prices = {}
        cover_signals = set()
        already_short = self.open_symbols()

        for symbol in SYMBOLS:
            cprint(f"\n🎯 Analyzing {symbol}...", "white", "on_cyan")

            df = hl.get_data(symbol, timeframe=TIMEFRAME, bars=BARS, add_indicators=True)
            if df.empty or len(df) < 60:
                cprint(f"❌ Not enough data for {symbol}, skipping", "red")
                continue

            price = float(df.iloc[-1]['close'])
            latest_prices[symbol] = price

            funding = hl.get_funding_rates(symbol)
            score, breakdown = self.score_short_setup(df, funding)

            cprint(f"📉 {symbol} bearish score: {score}/100", "yellow")
            for signal, pts in breakdown.items():
                if signal != 'funding_annualized_pct':
                    print(f"   • {signal}: {pts}")

            holding = symbol in already_short
            if score < SHORT_SCORE_THRESHOLD and not holding:
                cprint(f"😴 Score below {SHORT_SCORE_THRESHOLD} threshold - passing on {symbol}", "cyan")
                self._log_signal(symbol, score, breakdown, 'SKIPPED', 0, price)
                continue

            # Score cleared the bar (or we hold a position) - ask the AI
            summary = self.build_market_summary(symbol, df, funding, score, breakdown)
            action, confidence, reasoning = self.ask_ai(summary)
            cprint(f"\n🤖 AI verdict for {symbol}: {action} (confidence {confidence}%)", "white", "on_green")
            print(reasoning[:600])
            self._log_signal(symbol, score, breakdown, action, confidence, price)

            if action == 'COVER' and holding:
                cover_signals.add(symbol)
            elif action == 'SHORT' and not holding:
                if confidence < AI_CONFIDENCE_THRESHOLD:
                    cprint(f"🤔 Confidence {confidence}% below {AI_CONFIDENCE_THRESHOLD}% bar - passing", "yellow")
                elif len(self.open_symbols()) >= MAX_OPEN_SHORTS:
                    cprint(f"🚫 Already at max {MAX_OPEN_SHORTS} open shorts - passing", "yellow")
                else:
                    self.open_paper_short(symbol, price, confidence)

            time.sleep(1)  # be nice to the APIs

        self.manage_open_positions(latest_prices, cover_signals)
        self.print_performance()
        cprint("\n✨ Short Agent cycle complete! Moon Dev out! 🌙", "green")


def main():
    cprint("🌙 Moon Dev's Short Agent Starting Up! 🐻🚀", "white", "on_blue")
    cprint("⚠️ PAPER TRADING ONLY - no real orders are placed", "yellow")

    agent = ShortAgent()
    interval = SLEEP_BETWEEN_RUNS_MINUTES * 60

    while True:
        try:
            agent.run()
            next_run = datetime.now() + timedelta(minutes=SLEEP_BETWEEN_RUNS_MINUTES)
            cprint(f"\n⏳ Next hunt at {next_run.strftime('%Y-%m-%d %H:%M:%S')}", "white", "on_green")
            time.sleep(interval)
        except KeyboardInterrupt:
            cprint("\n👋 Short Agent shutting down gracefully... Moon Dev out! 🌙", "white", "on_blue")
            break
        except Exception as e:
            cprint(f"\n❌ Error in cycle: {str(e)}", "white", "on_red")
            time.sleep(interval)


if __name__ == "__main__":
    main()
