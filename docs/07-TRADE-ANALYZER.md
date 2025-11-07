# 📖 07 - Trade Analyzer (AI-Powered)

> **GPT-4o-mini Analysis: Prediction vs Reality**

---

## 🤖 Overview Sistema AI Analysis

Il **Trade Analyzer** usa **OpenAI GPT-4o-mini** per analizzare OGNI trade chiuso, confrontando **predizione ML** con **realtà effettiva** per identificare pattern e migliorare il sistema.

```
TRADE ANALYSIS FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APERTURA TRADE
  ├─ Save TradeSnapshot
  │  • Prediction (BUY/SELL + confidence)
  │  • Ensemble votes (15m, 30m, 1h)
  │  • Entry price & features (RSI, MACD, ADX, etc)
  │  • Expected outcome
  └─ Store in SQLite DB

DURANTE TRADE
  └─ Track price path (ogni 15 min)

CHIUSURA TRADE
  ├─ Fetch snapshot from DB
  ├─ Calculate outcome (WIN/LOSS, ROE%, duration)
  ├─ Build comprehensive prompt
  └─ Call GPT-4o-mini API

ANALISI GPT-4o-mini
  ├─ Compare prediction vs reality
  ├─ Identify patterns (false breakout, news-driven, etc)
  ├─ Extract lessons learned
  └─ Provide actionable recommendations

OUTPUT
  ├─ Terminal logging (detailed report)
  ├─ SQLite storage (trade_analyses table)
  └─ JSON file (trade_analysis/{id}_analysis.json)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 💾 Data Structures

### **TradeSnapshot (At Opening)**

```python
@dataclass
class TradeSnapshot:
    """Snapshot completo al momento apertura"""
    symbol: str
    timestamp: str
    prediction_signal: str          # 'BUY' or 'SELL'
    ml_confidence: float            # 0.0-1.0
    ensemble_votes: Dict[str, str]  # {'15m': 'BUY', '30m': 'BUY', '1h': 'BUY'}
    entry_price: float
    entry_features: Dict[str, float]  # {rsi, macd, adx, atr, volume, etc}
    expected_target: float          # Expected TP%
    expected_risk: float            # Expected SL%
```

**Example**:
```json
{
  "symbol": "SOL/USDT:USDT",
  "timestamp": "2025-01-07T16:45:30",
  "prediction_signal": "BUY",
  "ml_confidence": 0.77,
  "ensemble_votes": {
    "15m": "BUY",
    "30m": "BUY",
    "1h": "BUY"
  },
  "entry_price": 100.50,
  "entry_features": {
    "rsi": 55.2,
    "macd": 0.15,
    "adx": 28.5,
    "atr": 2.3,
    "volume": 1250000,
    "volatility": 0.028
  }
}
```

### **TradeAnalysis (At Closing)**

```python
@dataclass
class TradeAnalysis:
    """Risultato analisi completa"""
    symbol: str
    timestamp: str
    outcome: str                      # 'WIN' or 'LOSS'
    pnl_roe: float                    # P&L in ROE%
    duration_minutes: int
    
    # Prediction vs Reality
    predicted_signal: str
    prediction_confidence: float
    prediction_accuracy: str          # 'correct_confident', 'overconfident', etc
    
    # LLM Analysis
    analysis_category: str            # 'perfect_execution', 'false_breakout', etc
    explanation: str                  # 2-3 sentences
    what_went_right: List[str]
    what_went_wrong: List[str]
    recommendations: List[str]
    ml_model_feedback: Dict[str, any]
    confidence: float                 # LLM analysis confidence
```

---

## 🎯 Analysis Triggers

### **Configuration**

```python
LLM_ANALYSIS_ENABLED = True       # Master switch
LLM_MODEL = 'gpt-4o-mini'         # Cost-effective model
LLM_ANALYZE_ALL_TRADES = False    # False = only wins+losses
LLM_ANALYZE_WINS = True           # Analyze winning trades
LLM_ANALYZE_LOSSES = True         # Analyze losing trades
LLM_MIN_TRADE_DURATION = 5        # Min 5 minutes duration
```

### **When Analysis Happens**

```python
def _should_analyze(outcome, pnl_roe, duration):
    """Decide se analizzare questo trade"""
    
    # Check minimum duration
    if duration < LLM_MIN_TRADE_DURATION:
        return False  # Too short
    
    # Analyze all if configured
    if LLM_ANALYZE_ALL_TRADES:
        return True
    
    # Selective analysis
    if outcome == 'WIN' and LLM_ANALYZE_WINS:
        return True
    
    if outcome == 'LOSS' and LLM_ANALYZE_LOSSES:
        return True
    
    return False
```

---

## 📝 Prompt Construction

### **Comprehensive Prompt Template**

```python
def _build_comprehensive_prompt(snapshot, outcome, pnl_roe, exit_price, duration):
    """
    Costruisce prompt dettagliato per GPT-4o-mini
    """
    
    prompt = f"""
Analyze this COMPLETE TRADE comparing PREDICTION vs REALITY:

═══════════════════════════════════════════════════════════════════
PREDICTION (What ML expected)
═══════════════════════════════════════════════════════════════════

Symbol: {symbol_short}
Signal: {snapshot.prediction_signal}
ML Confidence: {snapshot.ml_confidence*100:.1f}%
Ensemble Votes: {json.dumps(snapshot.ensemble_votes, indent=2)}

Entry Price: ${snapshot.entry_price:.4f}
Entry Features:
  - RSI: {entry_features['rsi']:.1f}
  - MACD: {entry_features['macd']:.4f}
  - ADX (trend): {entry_features['adx']:.1f}
  - ATR (volatility): {entry_features['atr']:.4f}
  - Volume: {entry_features['volume']:,.0f}

Expected Outcome: {"Profit" if snapshot.prediction_signal == 'BUY' else "Decline"}

═══════════════════════════════════════════════════════════════════
REALITY (What actually happened)
═══════════════════════════════════════════════════════════════════

Outcome: {outcome}
PnL: {pnl_roe:+.1f}% ROE
Exit Price: ${exit_price:.4f} ({price_change_pct:+.2f}% price change)
Duration: {duration} minutes

PRICE PATH:
{price_path_str}

═══════════════════════════════════════════════════════════════════
ANALYSIS REQUIRED
═══════════════════════════════════════════════════════════════════

Provide comprehensive JSON analysis with:

1. "prediction_accuracy": Choose ONE:
   - "correct_confident": Prediction correct, confidence appropriate
   - "correct_underconfident": Prediction correct but confidence too low
   - "overconfident": Wrong prediction or confidence too high vs result
   - "completely_wrong": Prediction direction wrong

2. "analysis_category": Choose ONE:
   - "perfect_execution": Everything went as expected
   - "lucky_win": Won but for wrong reasons
   - "unlucky_loss": Good trade but external factors
   - "false_breakout": Technical pattern failed
   - "news_driven": News event changed outcome
   - "stop_hunt": Market maker manipulation
   - "high_volatility": Excessive volatility
   - "weak_trend": Trend insufficient
   - "btc_correlation": BTC movement impact

3. "explanation": 2-3 sentences explaining prediction vs reality

4. "what_went_right": Array of things that worked (even if loss)

5. "what_went_wrong": Array of things that didn't work (even if win)

6. "recommendations": 3-5 actionable improvements

7. "ml_model_feedback": Object with:
   - "features_to_emphasize": [features that were predictive]
   - "features_to_reduce": [features that misled]
   - "confidence_adjustment": "increase/decrease/maintain"
   - "suggested_threshold": numerical value if applicable

8. "confidence": Your confidence in this analysis (0.0-1.0)

Focus on LEARNING both from wins and losses. Be specific and actionable.
"""
    
    return prompt
```

---

## 🔮 GPT-4o-mini API Call

### **Request**

```python
response = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[
        {
            "role": "system",
            "content": "You are an expert quantitative analyst specializing in cryptocurrency trading and machine learning. Analyze trade outcomes by comparing predictions versus reality to improve future performance."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    response_format={"type": "json_object"},  # Force JSON output
    temperature=0.3,  # Lower = more deterministic
    max_tokens=1500
)
```

### **Response Parsing**

```python
# Parse JSON response
analysis_data = json.loads(response.choices[0].message.content)

# Extract fields
analysis = TradeAnalysis(
    symbol=symbol,
    timestamp=datetime.now().isoformat(),
    outcome=outcome,
    pnl_roe=pnl_roe,
    duration_minutes=duration,
    predicted_signal=snapshot.prediction_signal,
    prediction_confidence=snapshot.ml_confidence,
    prediction_accuracy=analysis_data['prediction_accuracy'],
    analysis_category=analysis_data['analysis_category'],
    explanation=analysis_data['explanation'],
    what_went_right=analysis_data['what_went_right'],
    what_went_wrong=analysis_data['what_went_wrong'],
    recommendations=analysis_data['recommendations'],
    ml_model_feedback=analysis_data['ml_model_feedback'],
    confidence=analysis_data['confidence']
)
```

---

## 📊 Example Analysis Output

### **Terminal Logging**

```
════════════════════════════════════════════════════════════════════════════════
🤖 TRADE ANALYSIS: SOL ✅
════════════════════════════════════════════════════════════════════════════════
📊 Outcome: WIN | PnL: +8.5% ROE | Duration: 45min
🎯 Prediction: BUY @ 77% confidence | Accuracy: correct_confident
📊 Category: perfect_execution

💡 Explanation:
   The ML prediction was accurate with strong ensemble agreement across all timeframes.
   The trade executed as expected with RSI confirmation and ADX showing strong trend.
   Exit at +8.5% ROE demonstrates good profit-taking discipline.

✅ What Went Right:
   • Strong ensemble agreement (15m: 72%, 30m: 78%, 1h: 81%) provided high confidence
   • RSI at 55.2 showed momentum without being overbought
   • ADX at 28.5 confirmed strong trend strength
   • Volume spike validated the breakout
   • Disciplined exit captured profit before potential reversal

❌ What Went Wrong:
   • Could have held longer - price continued to $105 (+10% total)
   • Initial entry timing could be refined (entered near M5 resistance)

🎯 Recommendations:
   1. Consider partial exits strategy to capture extended moves
   2. Add volume profile analysis for better entry timing
   3. Monitor 4h timeframe for longer-term trend confirmation
   4. Implement trailing stop for runners beyond +10% ROE
   5. Track correlation with BTC for exit timing optimization

🧠 ML Model Feedback:
   📈 Emphasize: RSI, ADX, ensemble_agreement, volume_spike
   📉 Reduce: None identified
   ⚙️ Confidence: increase (proven reliable in this setup)

🔍 Analysis Confidence: 85%
════════════════════════════════════════════════════════════════════════════════
```

### **JSON File Output**

```json
{
  "position_id": "pos_abc123",
  "symbol": "SOL/USDT:USDT",
  "timestamp": "2025-01-07T17:30:45",
  "outcome": "WIN",
  "pnl_roe": 8.5,
  "duration_minutes": 45,
  "prediction": {
    "signal": "BUY",
    "confidence": 0.77,
    "ensemble_votes": {
      "15m": "BUY",
      "30m": "BUY",
      "1h": "BUY"
    },
    "entry_features": {
      "rsi": 55.2,
      "macd": 0.15,
      "adx": 28.5,
      "atr": 2.3,
      "volume": 1250000,
      "volatility": 0.028
    }
  },
  "analysis": {
    "accuracy": "correct_confident",
    "category": "perfect_execution",
    "summary": "The ML prediction was accurate with strong ensemble agreement...",
    "what_went_right": [
      "Strong ensemble agreement provided high confidence",
      "RSI showed momentum without being overbought",
      "ADX confirmed strong trend strength",
      "Volume spike validated the breakout",
      "Disciplined exit captured profit"
    ],
    "what_went_wrong": [
      "Could have held longer - price continued higher",
      "Entry timing near resistance could be refined"
    ],
    "recommendations": [
      "Consider partial exits strategy",
      "Add volume profile analysis",
      "Monitor 4h timeframe",
      "Implement trailing stop",
      "Track BTC correlation"
    ],
    "ml_feedback": {
      "features_to_emphasize": ["RSI", "ADX", "ensemble_agreement", "volume_spike"],
      "features_to_reduce": [],
      "confidence_adjustment": "increase",
      "suggested_threshold": null
    },
    "confidence": 0.85
  }
}
```

---

## 📈 Learning Insights Aggregation

### **Get Aggregated Feedback**

```python
def get_learning_insights(lookback_days=30):
    """
    Aggrega analisi per identificare pattern ricorrenti
    """
    
    # Query database
    analyses = query_last_n_days(lookback_days)
    
    # Aggregate
    accuracy_breakdown = Counter([a.prediction_accuracy for a in analyses])
    category_breakdown = Counter([a.analysis_category for a in analyses])
    
    # Feature importance
    all_emphasize = []
    all_reduce = []
    for a in analyses:
        all_emphasize.extend(a.ml_feedback.get('features_to_emphasize', []))
        all_reduce.extend(a.ml_feedback.get('features_to_reduce', []))
    
    feature_emphasize_counts = Counter(all_emphasize)
    feature_reduce_counts = Counter(all_reduce)
    
    return {
        'total_analyses': len(analyses),
        'accuracy_breakdown': dict(accuracy_breakdown),
        'category_breakdown': dict(category_breakdown),
        'top_features_to_emphasize': feature_emphasize_counts.most_common(5),
        'top_features_to_reduce': feature_reduce_counts.most_common(5)
    }
```

### **Learning Report Example**

```
════════════════════════════════════════════════════════════════════════════════
🤖 TRADE ANALYSIS LEARNING REPORT (Last 30 days)
════════════════════════════════════════════════════════════════════════════════

📊 Total Analyses: 45

🎯 PREDICTION ACCURACY:
   • correct_confident: 25 (55.6%)
   • correct_underconfident: 8 (17.8%)
   • overconfident: 10 (22.2%)
   • completely_wrong: 2 (4.4%)

📈 TRADE CATEGORIES:
   • perfect_execution: 18
   • false_breakout: 12
   • high_volatility: 6
   • unlucky_loss: 5
   • news_driven: 4

📈 TOP FEATURES TO EMPHASIZE:
   • ADX: 28 recommendations
   • RSI: 25 recommendations
   • ensemble_agreement: 22 recommendations
   • volume_spike: 18 recommendations
   • trend_strength: 15 recommendations

📉 TOP FEATURES TO REDUCE:
   • stoch_rsi: 8 recommendations (misleading in ranging markets)
   • macd_histogram: 6 recommendations (lagging signal)
   • bollinger_squeeze: 5 recommendations (false signals)

════════════════════════════════════════════════════════════════════════════════
```

---

## 💰 Cost Analysis

### **GPT-4o-mini Pricing**

```
Model: gpt-4o-mini
Input: $0.150 / 1M tokens
Output: $0.600 / 1M tokens

Average per Trade:
  Input tokens: ~1,200 (prompt)
  Output tokens: ~800 (analysis)
  
  Cost = (1200 × $0.150 + 800 × $0.600) / 1,000,000
  Cost = ($0.18 + $0.48) / 1,000,000
  Cost = $0.00066 per trade
  Cost ≈ $0.0006 per trade

Monthly Estimates:
  100 trades/month: $0.06
  500 trades/month: $0.30
  1000 trades/month: $0.60
```

**Conclusion**: Estremamente cost-effective per il valore fornito!

---

## ⚙️ Configuration

```python
# Master switch
LLM_ANALYSIS_ENABLED = True

# Model selection
LLM_MODEL = 'gpt-4o-mini'  # Cost-effective

# Analysis triggers
LLM_ANALYZE_ALL_TRADES = False  # False = selective
LLM_ANALYZE_WINS = True         # Analyze wins
LLM_ANALYZE_LOSSES = True       # Analyze losses
LLM_MIN_TRADE_DURATION = 5      # Min 5 minutes

# Price tracking
TRACK_PRICE_SNAPSHOTS = True
PRICE_SNAPSHOT_INTERVAL = 900   # Every 15 minutes

# Storage
DATABASE_FILE = "trade_analysis.db"
JSON_OUTPUT_DIR = "trade_analysis/"
```

---

## 🔧 Database Schema

```sql
-- Trade snapshots (at opening)
CREATE TABLE trade_snapshots (
    id INTEGER PRIMARY KEY,
    position_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    prediction_signal TEXT,
    ml_confidence REAL,
    ensemble_votes TEXT,  -- JSON
    entry_price REAL,
    entry_features TEXT,  -- JSON
    price_snapshots TEXT, -- JSON array
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Trade analyses (at closing)
CREATE TABLE trade_analyses (
    id INTEGER PRIMARY KEY,
    position_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    outcome TEXT,
    pnl_roe REAL,
    duration_minutes INTEGER,
    prediction_accuracy TEXT,
    analysis_category TEXT,
    explanation TEXT,
    recommendations TEXT,  -- JSON array
    ml_feedback TEXT,      -- JSON object
    confidence REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES trade_snapshots(position_id)
);

-- Indexes
CREATE INDEX idx_symbol_outcome ON trade_analyses(symbol, outcome);
CREATE INDEX idx_category ON trade_analyses(analysis_category);
CREATE INDEX idx_accuracy ON trade_analyses(prediction_accuracy);
```

---

## 📚 Next Steps

- **08-POSITION-MANAGEMENT.md** - Thread-safe position tracking
- **09-DASHBOARD.md** - PyQt6 real-time GUI
- **10-CONFIGURAZIONE.md** - Complete config guide

---

**🎯 KEY TAKEAWAY**: Il Trade Analyzer con GPT-4o-mini fornisce feedback intelligente post-trade a costo quasi zero (~$0.0006/trade), identificando pattern perdenti e suggerendo miglioramenti actionable per auto-tuning continuo del sistema.
