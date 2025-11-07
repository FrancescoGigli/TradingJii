#!/usr/bin/env python3
"""
🤖 TRADE ANALYZER - AI-POWERED PREDICTION VS REALITY

Sistema intelligente che analizza TUTTI i trade (win E loss) usando OpenAI GPT.
Confronta predizione ML vs realtà, analizza price path, identifica pattern.

FEATURES:
- Analisi completa ogni trade chiuso (win OR loss)
- Snapshot predizione al momento apertura
- Price path tracking ogni 15min
- Confronto predizione vs realtà
- Pattern recognition per auto-tuning
- Cost-effective: GPT-4o-mini (~$0.0006 per trade)
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from termcolor import colored

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("⚠️ OpenAI library not installed. Run: pip install openai")


@dataclass
class TradeSnapshot:
    """Snapshot completo trade al momento apertura"""
    symbol: str
    timestamp: str
    prediction_signal: str  # BUY or SELL
    ml_confidence: float
    ensemble_votes: Dict[str, str]  # {'15m': 'BUY', '30m': 'BUY', '1h': 'NEUTRAL'}
    entry_price: float
    entry_features: Dict[str, float]  # RSI, MACD, ADX, volume, etc
    expected_target: float  # Expected TP%
    expected_risk: float  # Expected SL%


@dataclass
class TradeAnalysis:
    """Risultato analisi completa trade con feedback quantitativo"""
    symbol: str
    timestamp: str
    outcome: str  # WIN or LOSS
    pnl_roe: float
    duration_minutes: int
    
    # Predizione vs Realtà
    predicted_signal: str
    prediction_confidence: float
    prediction_accuracy: str  # correct_confident, overconfident, underconfident, completely_wrong
    
    # Analisi LLM
    analysis_category: str
    explanation: str
    what_went_right: List[str]
    what_went_wrong: List[str]
    recommendations: List[str]
    ml_model_feedback: Dict[str, any]
    confidence: float
    
    # 🆕 Quantitative feedback (for auto-tuning)
    risk_level: float = 0.5  # 0.0-1.0 (how risky this trade was)
    confidence_adjustment: float = 0.0  # -0.2 to +0.2 (suggested adjustment for future)
    features_weight_adjustment: Dict[str, float] = None  # Feature -> weight change percentage


class TradeAnalyzer:
    """
    Analizzatore intelligente predizione vs realtà con OpenAI
    """
    
    def __init__(self, config):
        """
        Inizializza analyzer
        
        Args:
            config: Config module
        """
        self.config = config
        self.enabled = getattr(config, 'LLM_ANALYSIS_ENABLED', False)
        
        if not self.enabled:
            logging.info("🤖 Trade Analyzer: DISABLED")
            return
        
        if not OPENAI_AVAILABLE:
            logging.error("❌ OpenAI library not available - disabling analyzer")
            self.enabled = False
            return
        
        # API Configuration
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logging.error("❌ OPENAI_API_KEY not found in environment")
            self.enabled = False
            return
        
        try:
            self.client = OpenAI(api_key=api_key)
            self.model = getattr(config, 'LLM_MODEL', 'gpt-4o-mini')
            
            # Analysis triggers
            self.analyze_all_trades = getattr(config, 'LLM_ANALYZE_ALL_TRADES', False)
            self.analyze_wins = getattr(config, 'LLM_ANALYZE_WINS', True)
            self.analyze_losses = getattr(config, 'LLM_ANALYZE_LOSSES', True)
            self.min_trade_duration = getattr(config, 'LLM_MIN_TRADE_DURATION', 5)  # Min 5min
            
            # Database setup
            self.db_path = Path("trade_analysis.db")
            self._init_database()
            
            logging.info(colored(
                f"🤖 Trade Analyzer: ENABLED | Model: {self.model} | "
                f"Analyze: {'ALL trades' if self.analyze_all_trades else 'Wins+Losses'}",
                "green", attrs=['bold']
            ))
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize OpenAI client: {e}")
            self.enabled = False
    
    def _init_database(self):
        """Inizializza database SQLite per tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table per trade snapshots (al momento apertura)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    prediction_signal TEXT,
                    ml_confidence REAL,
                    ensemble_votes TEXT,
                    entry_price REAL,
                    entry_features TEXT,
                    price_snapshots TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table per trade analyses (alla chiusura)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    outcome TEXT,
                    pnl_roe REAL,
                    duration_minutes INTEGER,
                    prediction_accuracy TEXT,
                    analysis_category TEXT,
                    explanation TEXT,
                    recommendations TEXT,
                    ml_feedback TEXT,
                    confidence REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (position_id) REFERENCES trade_snapshots(position_id)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_outcome 
                ON trade_analyses(symbol, outcome)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category 
                ON trade_analyses(analysis_category)
            """)
            
            conn.commit()
            conn.close()
            
            logging.debug("💾 Trade analysis database initialized")
            
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
    
    def save_trade_snapshot(
        self,
        position_id: str,
        snapshot: TradeSnapshot
    ):
        """
        Salva snapshot trade all'apertura
        
        Args:
            position_id: ID univoco posizione
            snapshot: TradeSnapshot object
        """
        if not self.enabled:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO trade_snapshots
                (position_id, symbol, timestamp, prediction_signal, ml_confidence,
                 ensemble_votes, entry_price, entry_features, price_snapshots)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_id,
                snapshot.symbol,
                snapshot.timestamp,
                snapshot.prediction_signal,
                snapshot.ml_confidence,
                json.dumps(snapshot.ensemble_votes),
                snapshot.entry_price,
                json.dumps(snapshot.entry_features),
                json.dumps([])  # Empty price snapshots list initially
            ))
            
            conn.commit()
            conn.close()
            
            logging.debug(f"💾 Trade snapshot saved for {position_id}")
            
        except Exception as e:
            logging.error(f"Failed to save trade snapshot: {e}")
    
    def add_price_snapshot(
        self,
        position_id: str,
        price: float,
        volume: float,
        timestamp: str
    ):
        """
        Aggiungi price snapshot durante vita trade
        
        Args:
            position_id: ID posizione
            price: Prezzo corrente
            volume: Volume corrente
            timestamp: Timestamp snapshot
        """
        if not self.enabled:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get existing snapshots
            cursor.execute(
                "SELECT price_snapshots FROM trade_snapshots WHERE position_id = ?",
                (position_id,)
            )
            
            row = cursor.fetchone()
            if row:
                snapshots = json.loads(row[0]) if row[0] else []
                snapshots.append({
                    'timestamp': timestamp,
                    'price': price,
                    'volume': volume
                })
                
                # Update
                cursor.execute(
                    "UPDATE trade_snapshots SET price_snapshots = ? WHERE position_id = ?",
                    (json.dumps(snapshots), position_id)
                )
                
                conn.commit()
            
            conn.close()
            
        except Exception as e:
            logging.debug(f"Failed to add price snapshot: {e}")
    
    async def analyze_complete_trade(
        self,
        position_id: str,
        outcome: str,  # WIN or LOSS
        pnl_roe: float,
        exit_price: float,
        duration_minutes: int
    ) -> Optional[TradeAnalysis]:
        """
        Analizza trade completo confrontando predizione vs realtà
        
        Args:
            position_id: ID posizione
            outcome: WIN o LOSS
            pnl_roe: PnL in ROE%
            exit_price: Prezzo exit
            duration_minutes: Durata trade in minuti
            
        Returns:
            TradeAnalysis object se successful
        """
        if not self.enabled:
            return None
        
        # Check se deve analizzare questo trade
        if not self._should_analyze(outcome, pnl_roe, duration_minutes):
            return None
        
        try:
            # Retrieve snapshot from DB
            snapshot_data = self._get_trade_snapshot(position_id)
            if not snapshot_data:
                logging.warning(f"⚠️ No snapshot found for {position_id}")
                return None
            
            symbol = snapshot_data['symbol']
            symbol_short = symbol.replace('/USDT:USDT', '')
            
            logging.info(colored(
                f"🤖 Analyzing complete trade for {symbol_short} ({outcome}, {pnl_roe:+.1f}% ROE)...",
                "cyan", attrs=['bold']
            ))
            
            # 🆕 Get market context (BTC trend, volatility, etc)
            market_context = await self._get_market_context(snapshot_data['timestamp'])
            
            # 🆕 Get previous trades for this symbol
            previous_trades = self._get_previous_trades(symbol, limit=3)
            
            # Build comprehensive prompt with enhanced context
            prompt = self._build_comprehensive_prompt(
                snapshot_data,
                outcome,
                pnl_roe,
                exit_price,
                duration_minutes,
                market_context,
                previous_trades
            )
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
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
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1500
            )
            
            # Parse response
            analysis_data = json.loads(response.choices[0].message.content)
            
            # Create TradeAnalysis object
            analysis = TradeAnalysis(
                symbol=symbol,
                timestamp=datetime.now().isoformat(),
                outcome=outcome,
                pnl_roe=pnl_roe,
                duration_minutes=duration_minutes,
                predicted_signal=snapshot_data['prediction_signal'],
                prediction_confidence=snapshot_data['ml_confidence'],
                prediction_accuracy=analysis_data.get('prediction_accuracy', 'unknown'),
                analysis_category=analysis_data.get('analysis_category', 'unknown'),
                explanation=analysis_data.get('explanation', ''),
                what_went_right=analysis_data.get('what_went_right', []),
                what_went_wrong=analysis_data.get('what_went_wrong', []),
                recommendations=analysis_data.get('recommendations', []),
                ml_model_feedback=analysis_data.get('ml_model_feedback', {}),
                confidence=analysis_data.get('confidence', 0.5)
            )
            
            # Log analysis
            self._log_analysis(analysis)
            
            # Save to database
            self._save_analysis(position_id, analysis)
            
            # 🆕 Save to JSON file
            self._save_analysis_file(position_id, analysis, snapshot_data)
            
            return analysis
            
        except Exception as e:
            logging.error(f"❌ Trade analysis failed for {position_id}: {e}")
            return None
    
    def _should_analyze(self, outcome: str, pnl_roe: float, duration_minutes: int) -> bool:
        """Determina se deve analizzare questo trade"""
        # Check minimum duration
        if duration_minutes < self.min_trade_duration:
            return False
        
        # Analyze all if configured
        if self.analyze_all_trades:
            return True
        
        # Analyze based on outcome
        if outcome == 'WIN' and self.analyze_wins:
            return True
        
        if outcome == 'LOSS' and self.analyze_losses:
            return True
        
        return False
    
    def _get_trade_snapshot(self, position_id: str) -> Optional[Dict]:
        """Retrieve trade snapshot from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM trade_snapshots WHERE position_id = ?",
                (position_id,)
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return {
                'position_id': row[1],
                'symbol': row[2],
                'timestamp': row[3],
                'prediction_signal': row[4],
                'ml_confidence': row[5],
                'ensemble_votes': json.loads(row[6]) if row[6] else {},
                'entry_price': row[7],
                'entry_features': json.loads(row[8]) if row[8] else {},
                'price_snapshots': json.loads(row[9]) if row[9] else []
            }
            
        except Exception as e:
            logging.error(f"Failed to get trade snapshot: {e}")
            return None
    
    async def _get_market_context(self, trade_timestamp: str) -> Dict:
        """
        Get market context at trade time (BTC trend, volatility, etc)
        
        Returns:
            Dict with market context data
        """
        try:
            # For now return placeholder - can be enhanced to fetch real BTC data
            return {
                'btc_trend': 'neutral',
                'market_volatility': 'moderate',
                'global_sentiment': 'neutral'
            }
        except Exception as e:
            logging.debug(f"Failed to get market context: {e}")
            return {}
    
    def _get_previous_trades(self, symbol: str, limit: int = 3) -> List[Dict]:
        """
        Get previous trades for the same symbol
        
        Args:
            symbol: Symbol to query
            limit: Max number of previous trades
            
        Returns:
            List of previous trade analyses
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT outcome, pnl_roe, prediction_accuracy, analysis_category
                FROM trade_analyses
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (symbol, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            previous_trades = []
            for row in rows:
                previous_trades.append({
                    'outcome': row[0],
                    'pnl_roe': row[1],
                    'accuracy': row[2],
                    'category': row[3]
                })
            
            return previous_trades
            
        except Exception as e:
            logging.debug(f"Failed to get previous trades: {e}")
            return []
    
    def _build_comprehensive_prompt(
        self,
        snapshot: Dict,
        outcome: str,
        pnl_roe: float,
        exit_price: float,
        duration_minutes: int,
        market_context: Dict,
        previous_trades: List[Dict]
    ) -> str:
        """Costruisce prompt completo per LLM con enhanced context"""
        
        symbol_short = snapshot['symbol'].replace('/USDT:USDT', '')
        entry_features = snapshot.get('entry_features', {})
        price_snapshots = snapshot.get('price_snapshots', [])
        
        # Calculate price movement
        entry_price = snapshot['entry_price']
        price_change_pct = ((exit_price - entry_price) / entry_price) * 100
        
        # Build price path visualization
        price_path_str = self._format_price_path(price_snapshots, entry_price, exit_price)
        
        # Build previous trades context
        prev_trades_str = ""
        if previous_trades:
            prev_trades_str = "\n\nPREVIOUS TRADES (Same Symbol):\n"
            for i, trade in enumerate(previous_trades, 1):
                outcome_emoji = "✅" if trade['outcome'] == 'WIN' else "❌"
                prev_trades_str += f"  {i}. {outcome_emoji} {trade['outcome']}: {trade['pnl_roe']:+.1f}% ROE | Accuracy: {trade.get('accuracy', 'N/A')}\n"
        
        # Build market context
        market_ctx_str = ""
        if market_context:
            market_ctx_str = f"\n\nMARKET CONTEXT:\n  BTC Trend: {market_context.get('btc_trend', 'unknown')}\n  Volatility: {market_context.get('market_volatility', 'unknown')}\n  Sentiment: {market_context.get('global_sentiment', 'unknown')}"
        
        prompt = f"""
Analyze this COMPLETE TRADE comparing PREDICTION vs REALITY:

═══════════════════════════════════════════════════════════════════
PREDICTION (What ML expected)
═══════════════════════════════════════════════════════════════════

Symbol: {symbol_short}
Signal: {snapshot['prediction_signal']}
ML Confidence: {snapshot['ml_confidence']*100:.1f}%
Ensemble Votes: {json.dumps(snapshot.get('ensemble_votes', {}), indent=2)}

Entry Price: ${entry_price:.4f}
Entry Features:
  - RSI: {entry_features.get('rsi', 0):.1f}
  - MACD: {entry_features.get('macd', 0):.4f}
  - ADX (trend): {entry_features.get('adx', 0):.1f}
  - ATR (volatility): {entry_features.get('atr', 0):.4f}
  - Volume: {entry_features.get('volume', 0):,.0f}

Expected Outcome: {"Profit" if snapshot['prediction_signal'] == 'BUY' else "Decline"}

═══════════════════════════════════════════════════════════════════
REALITY (What actually happened)
═══════════════════════════════════════════════════════════════════

Outcome: {outcome}
PnL: {pnl_roe:+.1f}% ROE
Exit Price: ${exit_price:.4f} ({price_change_pct:+.2f}% price change)
Duration: {duration_minutes} minutes

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
    
    def _format_price_path(self, snapshots: List[Dict], entry: float, exit: float) -> str:
        """Formatta price path per visualizzazione"""
        if not snapshots:
            return f"Entry: ${entry:.4f} → Exit: ${exit:.4f} (no intermediate data)"
        
        lines = [f"Entry: ${entry:.4f}"]
        for snap in snapshots:
            price = snap.get('price', 0)
            time = snap.get('timestamp', 'unknown')
            change = ((price - entry) / entry) * 100
            lines.append(f"  {time}: ${price:.4f} ({change:+.2f}%)")
        lines.append(f"Exit: ${exit:.4f}")
        
        return "\n".join(lines)
    
    def _log_analysis(self, analysis: TradeAnalysis):
        """Log analisi completa nel terminale"""
        symbol_short = analysis.symbol.replace('/USDT:USDT', '')
        
        outcome_color = "green" if analysis.outcome == "WIN" else "red"
        outcome_emoji = "✅" if analysis.outcome == "WIN" else "❌"
        
        logging.info("=" * 100)
        logging.info(colored(
            f"🤖 TRADE ANALYSIS: {symbol_short} {outcome_emoji}",
            "cyan", attrs=['bold']
        ))
        logging.info(colored(
            f"📊 Outcome: {analysis.outcome} | PnL: {analysis.pnl_roe:+.1f}% ROE | Duration: {analysis.duration_minutes}min",
            outcome_color
        ))
        logging.info(colored(
            f"🎯 Prediction: {analysis.predicted_signal} @ {analysis.prediction_confidence*100:.0f}% confidence | "
            f"Accuracy: {analysis.prediction_accuracy}",
            "yellow"
        ))
        logging.info(colored(f"📊 Category: {analysis.analysis_category}", "white"))
        
        logging.info(colored(f"\n💡 Explanation:", "white"))
        logging.info(f"   {analysis.explanation}")
        
        if analysis.what_went_right:
            logging.info(colored(f"\n✅ What Went Right:", "green"))
            for item in analysis.what_went_right:
                logging.info(f"   • {item}")
        
        if analysis.what_went_wrong:
            logging.info(colored(f"\n❌ What Went Wrong:", "red"))
            for item in analysis.what_went_wrong:
                logging.info(f"   • {item}")
        
        logging.info(colored(f"\n🎯 Recommendations:", "cyan"))
        for i, rec in enumerate(analysis.recommendations, 1):
            logging.info(f"   {i}. {rec}")
        
        if analysis.ml_model_feedback:
            logging.info(colored(f"\n🧠 ML Model Feedback:", "magenta"))
            feedback = analysis.ml_model_feedback
            if feedback.get('features_to_emphasize'):
                logging.info(f"   📈 Emphasize: {', '.join(feedback['features_to_emphasize'])}")
            if feedback.get('features_to_reduce'):
                logging.info(f"   📉 Reduce: {', '.join(feedback['features_to_reduce'])}")
            if feedback.get('confidence_adjustment'):
                logging.info(f"   ⚙️ Confidence: {feedback['confidence_adjustment']}")
        
        logging.info(colored(f"\n🔍 Analysis Confidence: {analysis.confidence:.0%}", "cyan"))
        logging.info("=" * 100)
    
    def _save_analysis(self, position_id: str, analysis: TradeAnalysis):
        """Salva analisi in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trade_analyses
                (position_id, symbol, timestamp, outcome, pnl_roe, duration_minutes,
                 prediction_accuracy, analysis_category, explanation, recommendations,
                 ml_feedback, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_id,
                analysis.symbol,
                analysis.timestamp,
                analysis.outcome,
                analysis.pnl_roe,
                analysis.duration_minutes,
                analysis.prediction_accuracy,
                analysis.analysis_category,
                analysis.explanation,
                json.dumps(analysis.recommendations),
                json.dumps(analysis.ml_model_feedback),
                analysis.confidence
            ))
            
            conn.commit()
            conn.close()
            
            logging.debug(f"💾 Trade analysis saved for {position_id}")
            
        except Exception as e:
            logging.error(f"Failed to save analysis: {e}")
    
    def _save_analysis_file(self, position_id: str, analysis: TradeAnalysis, snapshot: Dict):
        """Save analysis to JSON file for easy access"""
        try:
            # Create directory if doesn't exist
            os.makedirs("trade_analysis", exist_ok=True)
            
            # Build complete data
            analysis_data = {
                'position_id': position_id,
                'symbol': analysis.symbol,
                'timestamp': analysis.timestamp,
                'outcome': analysis.outcome,
                'pnl_roe': analysis.pnl_roe,
                'duration_minutes': analysis.duration_minutes,
                'prediction': {
                    'signal': analysis.predicted_signal,
                    'confidence': analysis.prediction_confidence,
                    'ensemble_votes': snapshot.get('ensemble_votes', {}),
                    'entry_features': snapshot.get('entry_features', {})
                },
                'analysis': {
                    'accuracy': analysis.prediction_accuracy,
                    'category': analysis.analysis_category,
                    'summary': analysis.explanation,
                    'what_went_right': analysis.what_went_right,
                    'what_went_wrong': analysis.what_went_wrong,
                    'recommendations': analysis.recommendations,
                    'ml_feedback': analysis.ml_model_feedback,
                    'confidence': analysis.confidence
                }
            }
            
            # Save to file
            filepath = f"trade_analysis/{position_id}_analysis.json"
            with open(filepath, 'w') as f:
                json.dump(analysis_data, f, indent=2)
            
            logging.info(f"📄 Analysis file saved: {filepath}")
            
        except Exception as e:
            logging.error(f"Failed to save analysis file: {e}")
    
    def get_learning_insights(self, lookback_days: int = 30) -> Dict:
        """
        Ottieni insights aggregati da tutte le analisi
        
        Returns:
            Dict con pattern learning, ML feedback aggregato, etc
        """
        if not self.enabled:
            return {}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
            
            # Get all analyses
            cursor.execute("""
                SELECT prediction_accuracy, analysis_category, ml_feedback, outcome
                FROM trade_analyses
                WHERE timestamp >= ?
            """, (cutoff,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return {'total_analyses': 0}
            
            # Aggregate insights
            accuracy_counts = {}
            category_counts = {}
            all_features_emphasize = []
            all_features_reduce = []
            
            for row in rows:
                accuracy = row[0]
                category = row[1]
                ml_feedback_str = row[2]
                outcome = row[3]
                
                accuracy_counts[accuracy] = accuracy_counts.get(accuracy, 0) + 1
                category_counts[category] = category_counts.get(category, 0) + 1
                
                if ml_feedback_str:
                    feedback = json.loads(ml_feedback_str)
                    all_features_emphasize.extend(feedback.get('features_to_emphasize', []))
                    all_features_reduce.extend(feedback.get('features_to_reduce', []))
            
            # Count feature frequencies
            from collections import Counter
            feature_emphasize_counts = Counter(all_features_emphasize)
            feature_reduce_counts = Counter(all_features_reduce)
            
            return {
                'total_analyses': len(rows),
                'lookback_days': lookback_days,
                'prediction_accuracy_breakdown': accuracy_counts,
                'category_breakdown': category_counts,
                'top_features_to_emphasize': feature_emphasize_counts.most_common(5),
                'top_features_to_reduce': feature_reduce_counts.most_common(5)
            }
            
        except Exception as e:
            logging.error(f"Failed to get learning insights: {e}")
            return {}
    
    def print_learning_report(self, lookback_days: int = 30):
        """Stampa report learning insights"""
        insights = self.get_learning_insights(lookback_days)
        
        if not insights or insights.get('total_analyses', 0) == 0:
            logging.info(f"🤖 No trade analyses in last {lookback_days} days")
            return
        
        logging.info("=" * 100)
        logging.info(colored(
            f"🤖 TRADE ANALYSIS LEARNING REPORT (Last {lookback_days} days)",
            "cyan", attrs=['bold']
        ))
        logging.info("=" * 100)
        
        logging.info(colored(f"\n📊 Total Analyses: {insights['total_analyses']}", "yellow", attrs=['bold']))
        
        # Prediction accuracy
        if insights.get('prediction_accuracy_breakdown'):
            logging.info(colored(f"\n🎯 PREDICTION ACCURACY:", "green", attrs=['bold']))
            for accuracy, count in insights['prediction_accuracy_breakdown'].items():
                pct = (count / insights['total_analyses']) * 100
                logging.info(f"   • {accuracy}: {count} ({pct:.1f}%)")
        
        # Categories
        if insights.get('category_breakdown'):
            logging.info(colored(f"\n📈 TRADE CATEGORIES:", "cyan", attrs=['bold']))
            for category, count in sorted(insights['category_breakdown'].items(), 
                                         key=lambda x: x[1], reverse=True)[:5]:
                logging.info(f"   • {category}: {count}")
        
        # ML Feedback
        if insights.get('top_features_to_emphasize'):
            logging.info(colored(f"\n📈 TOP FEATURES TO EMPHASIZE:", "green", attrs=['bold']))
            for feature, count in insights['top_features_to_emphasize']:
                logging.info(f"   • {feature}: {count} recommendations")
        
        if insights.get('top_features_to_reduce'):
            logging.info(colored(f"\n📉 TOP FEATURES TO REDUCE:", "red", attrs=['bold']))
            for feature, count in insights['top_features_to_reduce']:
                logging.info(f"   • {feature}: {count} recommendations")
        
        logging.info("=" * 100)


# Global instance (initialized by trading engine)
global_trade_analyzer: Optional[TradeAnalyzer] = None


def initialize_trade_analyzer(config):
    """Inizializza global trade analyzer"""
    global global_trade_analyzer
    global_trade_analyzer = TradeAnalyzer(config)
    return global_trade_analyzer
