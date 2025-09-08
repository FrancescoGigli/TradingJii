#!/usr/bin/env python3
"""
🤖 REINFORCEMENT LEARNING SIGNAL FILTER

RL Agent che filtra i segnali XGBoost per migliorare le performance.
- Input: XGBoost signals + market context + portfolio state
- Output: Probability di eseguire il segnale (0-1)
- Training: Basato su PnL reali dei trade eseguiti
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import json
import os
import logging
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from termcolor import colored

class RLSignalFilter(nn.Module):
    """
    Neural Network per filtrare segnali XGBoost
    
    Architecture:
    - Input: 12 features (XGBoost + market + portfolio context)
    - Hidden: 32 → 16 neurons with ReLU
    - Output: 1 sigmoid (probability to execute)
    """
    
    def __init__(self, input_size=12, hidden_size=32):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),  # Regularization
            nn.Linear(hidden_size, 16),
            nn.ReLU(), 
            nn.Dropout(0.1),
            nn.Linear(16, 1),
            nn.Sigmoid()  # Output: 0-1 probability
        )
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize network weights"""
        for layer in self.network:
            if isinstance(layer, nn.Linear):
                torch.nn.init.xavier_uniform_(layer.weight)
                layer.bias.data.fill_(0.01)
    
    def forward(self, state):
        """Forward pass through network"""
        return self.network(state)

class RLTrainingManager:
    """
    Manager per training e inference del RL agent
    """
    
    def __init__(self, model_path="trained_models/rl_agent.pth"):
        self.model_path = Path(model_path)
        self.model_path.parent.mkdir(exist_ok=True)
        
        # Initialize model
        self.model = RLSignalFilter()
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.BCELoss()
        
        # Training history
        self.training_history = {
            'episodes': 0,
            'total_rewards': 0.0,
            'avg_reward_per_episode': 0.0,
            'last_update': datetime.now().isoformat()
        }
        
        # Experience replay buffer
        self.experience_buffer = []
        self.max_buffer_size = 10000
        
        # Thread safety locks
        self._buffer_lock = threading.Lock()
        self._model_lock = threading.Lock()
        
        # Load existing model if available
        self.load_model()
        
        # Execution threshold (tunable) - REDUCED for initial learning
        self.execution_threshold = 0.5  # Reduced from 0.7 to allow learning
        
        # Silenced: logging.info("🤖 RL Signal Filter initialized")
    
    def build_rl_state(self, signal_data: Dict, market_context: Dict, portfolio_state: Dict) -> np.ndarray:
        """
        Costruisce state vector per RL agent
        
        Args:
            signal_data: XGBoost signal info
            market_context: Market conditions
            portfolio_state: Current portfolio status
            
        Returns:
            np.ndarray: State vector (12 features)
        """
        try:
            # XGBoost signal info (4 features)
            tf_preds = signal_data.get('tf_predictions', {})
            xgb_features = [
                signal_data.get('confidence', 0.5),  # Ensemble confidence
                tf_preds.get('15m', 2) / 2.0,         # Normalize to 0-1
                tf_preds.get('30m', 2) / 2.0,
                tf_preds.get('1h', 2) / 2.0
            ]
            
            # Market context (4 features)
            market_features = [
                market_context.get('volatility', 0.5),     # ATR/price ratio
                market_context.get('volume_surge', 1.0),   # Volume vs average
                market_context.get('trend_strength', 25.0) / 100.0,  # ADX normalized
                market_context.get('rsi_position', 50.0) / 100.0     # RSI normalized
            ]
            
            # Portfolio state (4 features) 
            portfolio_features = [
                min(portfolio_state.get('available_balance_pct', 1.0), 1.0),  # Available balance %
                portfolio_state.get('active_positions', 0) / 10.0,            # Positions normalized
                np.tanh(portfolio_state.get('total_realized_pnl', 0.0) / 100.0),  # PnL normalized
                np.tanh(portfolio_state.get('unrealized_pnl_pct', 0.0) / 10.0)    # Unrealized PnL normalized
            ]
            
            # Combine all features
            state_vector = np.array(xgb_features + market_features + portfolio_features, dtype=np.float32)
            
            # Safety: ensure all values are finite and in reasonable range
            state_vector = np.nan_to_num(state_vector, nan=0.5, posinf=1.0, neginf=0.0)
            state_vector = np.clip(state_vector, 0.0, 1.0)
            
            return state_vector
            
        except Exception as e:
            logging.error(f"Error building RL state: {e}")
            # Fallback: neutral state
            return np.full(12, 0.5, dtype=np.float32)
    
    def should_execute_signal(self, signal_data: Dict, market_context: Dict, portfolio_state: Dict) -> Tuple[bool, float, Dict]:
        """
        Decide se eseguire un segnale XGBoost con ragioni dettagliate
        
        Returns:
            Tuple[bool, float, Dict]: (should_execute, confidence, decision_details)
        """
        try:
            # CRITICAL FIX: Add detailed logging for debugging
            symbol = signal_data.get('symbol', 'Unknown')
            logging.debug(f"🤖 RL analyzing signal for {symbol}")
            
            # Build state vector with error checking
            state = self.build_rl_state(signal_data, market_context, portfolio_state)
            logging.debug(f"🤖 RL state built successfully: {state[:4]}...")  # Log first 4 values
            
            # Get model prediction with error checking
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                execution_prob = self.model(state_tensor).item()
            
            logging.debug(f"🤖 RL model prediction: {execution_prob:.3f}")
            
            # Analyze decision factors for detailed feedback
            decision_details = self._analyze_decision_factors(signal_data, market_context, portfolio_state, execution_prob)
            
            # CRITICAL FIX: Validate decision_details integrity
            if not decision_details or 'primary_reason' not in decision_details:
                logging.error(f"🤖 RL decision_details invalid: {decision_details}")
                decision_details = self._create_fallback_details("Invalid decision details structure")
            
            # Decision based on threshold
            should_execute = execution_prob >= self.execution_threshold
            
            # ENHANCED LOGGING: Log decision with reasons
            verdict = "APPROVED" if should_execute else "REJECTED"
            primary_reason = decision_details.get('primary_reason', 'Unknown reason')
            logging.debug(f"🤖 RL Decision for {symbol}: {verdict} ({execution_prob:.1%}) - {primary_reason}")
            
            return should_execute, execution_prob, decision_details
            
        except Exception as e:
            logging.error(f"🤖 CRITICAL: RL decision error for {signal_data.get('symbol', 'Unknown')}: {e}")
            logging.error(f"🤖 RL Error details: {type(e).__name__}: {str(e)}")
            # Fallback: execute with moderate confidence (conservative)
            fallback_details = self._create_fallback_details(f"RL System Error: {str(e)[:50]}")
            return True, 0.6, fallback_details
    
    def _create_fallback_details(self, error_reason: str) -> Dict:
        """
        CRITICAL FIX: Create properly structured fallback details
        
        Args:
            error_reason: Reason for fallback
            
        Returns:
            Dict: Properly structured decision details
        """
        return {
            'factors': {
                'error_mode': {
                    'value': 'Fallback Active',
                    'threshold': 'N/A',
                    'status': 'ERROR'
                }
            },
            'approvals': ['Using fallback approval mode'],
            'issues': [error_reason],
            'primary_reason': error_reason,
            'final_verdict': 'APPROVED (Fallback)',
            'execution_probability': 0.6
        }
    
    def _analyze_decision_factors(self, signal_data: Dict, market_context: Dict, portfolio_state: Dict, execution_prob: float) -> Dict:
        """
        Analizza i fattori che influenzano la decisione RL per feedback dettagliato
        
        Returns:
            Dict: Detailed breakdown of decision factors
        """
        try:
            factors = {}
            issues = []
            approvals = []
            
            # 1. Signal Strength Analysis
            signal_confidence = signal_data.get('confidence', 0.0)
            signal_threshold = 0.65  # Minimum signal confidence
            
            factors['signal_strength'] = {
                'value': f"{signal_confidence:.1%}",
                'threshold': f"{signal_threshold:.1%}",
                'status': 'OK' if signal_confidence >= signal_threshold else 'TOO_LOW'
            }
            
            if signal_confidence >= signal_threshold:
                approvals.append(f"Signal strength {signal_confidence:.1%} ≥ {signal_threshold:.1%}")
            else:
                issues.append(f"Signal too weak: {signal_confidence:.1%} < {signal_threshold:.1%}")
            
            # 2. Market Volatility Analysis
            volatility = market_context.get('volatility', 0.02)
            volatility_threshold = 0.05  # 5% max volatility
            volatility_pct = volatility * 100
            
            factors['market_volatility'] = {
                'value': f"{volatility_pct:.1f}%",
                'threshold': f"{volatility_threshold * 100:.1f}%",
                'status': 'OK' if volatility <= volatility_threshold else 'TOO_HIGH'
            }
            
            if volatility <= volatility_threshold:
                approvals.append(f"Volatility {volatility_pct:.1f}% ≤ {volatility_threshold * 100:.1f}%")
            else:
                issues.append(f"High volatility: {volatility_pct:.1f}% > {volatility_threshold * 100:.1f}%")
            
            # 3. Market Trend Analysis
            trend_strength = market_context.get('trend_strength', 25.0)
            trend_threshold = 20.0  # Minimum ADX for trend
            
            factors['trend_strength'] = {
                'value': f"{trend_strength:.1f}",
                'threshold': f"{trend_threshold:.1f}",
                'status': 'STRONG' if trend_strength >= trend_threshold else 'WEAK'
            }
            
            if trend_strength >= trend_threshold:
                approvals.append(f"Strong trend ADX {trend_strength:.1f} ≥ {trend_threshold:.1f}")
            else:
                issues.append(f"Weak trend: ADX {trend_strength:.1f} < {trend_threshold:.1f}")
            
            # 4. Portfolio Risk Analysis  
            available_balance_pct = portfolio_state.get('available_balance', 1000.0) / portfolio_state.get('wallet_balance', 1000.0)
            balance_threshold = 0.1  # Minimum 10% available balance
            
            factors['available_balance'] = {
                'value': f"{available_balance_pct:.1%}",
                'threshold': f"{balance_threshold:.1%}",
                'status': 'OK' if available_balance_pct >= balance_threshold else 'LOW'
            }
            
            if available_balance_pct >= balance_threshold:
                approvals.append(f"Available balance {available_balance_pct:.1%} ≥ {balance_threshold:.1%}")
            else:
                issues.append(f"Low available balance: {available_balance_pct:.1%} < {balance_threshold:.1%}")
            
            # 5. RL Model Confidence Analysis
            rl_threshold = self.execution_threshold
            
            factors['rl_confidence'] = {
                'value': f"{execution_prob:.1%}",
                'threshold': f"{rl_threshold:.1%}",
                'status': 'HIGH' if execution_prob >= rl_threshold else 'LOW'
            }
            
            if execution_prob >= rl_threshold:
                approvals.append(f"RL confidence {execution_prob:.1%} ≥ {rl_threshold:.1%}")
            else:
                issues.append(f"Low RL confidence: {execution_prob:.1%} < {rl_threshold:.1%}")
            
            # Determine primary reason
            if not issues:
                primary_reason = "All conditions favorable"
                final_verdict = "APPROVED"
            else:
                primary_reason = issues[0]  # Most critical issue
                final_verdict = "REJECTED"
            
            return {
                'factors': factors,
                'approvals': approvals,
                'issues': issues,
                'primary_reason': primary_reason,
                'final_verdict': final_verdict,
                'execution_probability': execution_prob
            }
            
        except Exception as e:
            logging.error(f"Error analyzing RL decision factors: {e}")
            return {
                'factors': {},
                'approvals': [],
                'issues': [f"Analysis error: {e}"],
                'primary_reason': 'Analysis failed',
                'final_verdict': 'ERROR',
                'execution_probability': 0.0
            }
    
    def record_trade_result(self, state: np.ndarray, action: bool, reward: float):
        """
        Record trade result for learning
        
        Args:
            state: RL state when decision was made
            action: True if executed, False if skipped
            reward: Calculated reward from trade result
        """
        try:
            experience = {
                'state': state.tolist(),
                'action': float(action),  # Convert bool to float for training
                'reward': reward,
                'timestamp': datetime.now().isoformat()
            }
            
            # Add to experience buffer
            self.experience_buffer.append(experience)
            
            # Maintain buffer size limit
            if len(self.experience_buffer) > self.max_buffer_size:
                self.experience_buffer = self.experience_buffer[-self.max_buffer_size:]
            
            logging.debug(f"📝 RL experience recorded: action={action}, reward={reward:.3f}")
            
        except Exception as e:
            logging.error(f"Error recording RL experience: {e}")
    
    def calculate_reward(self, trade_result: Dict, portfolio_state: Dict) -> float:
        """
        Calculate reward for RL learning
        
        Args:
            trade_result: Trade outcome (PnL, duration, etc.)
            portfolio_state: Portfolio status after trade
            
        Returns:
            float: Reward value (-1.0 to +1.0)
        """
        try:
            base_reward = 0.0
            
            # Primary reward: Trade PnL (main component)
            pnl_pct = trade_result.get('final_pnl_pct', 0.0)
            base_reward += np.tanh(pnl_pct / 10.0)  # Normalize to -1 to +1
            
            # Bonus for winning trades
            if pnl_pct > 0:
                base_reward += 0.1
            
            # Penalty for large losses
            if pnl_pct < -2.0:
                base_reward -= 0.2
            
            # Portfolio efficiency bonus
            win_rate = portfolio_state.get('win_rate', 0.0)
            if win_rate > 60.0:
                base_reward += 0.05  # Bonus for high win rate
            elif win_rate < 40.0:
                base_reward -= 0.05  # Penalty for low win rate
            
            # Risk management penalty
            total_pnl = portfolio_state.get('total_realized_pnl', 0.0)
            if total_pnl < -5.0:  # Session drawdown > 5%
                base_reward -= 0.1
            
            # Clip final reward to valid range
            return np.clip(base_reward, -1.0, 1.0)
            
        except Exception as e:
            logging.error(f"Error calculating RL reward: {e}")
            return 0.0  # Neutral reward on error
    
    def update_model(self, batch_size=64):
        """
        Thread-safe RL model update with experience replay
        
        Args:
            batch_size: Number of experiences to sample for training
        """
        try:
            # Thread-safe buffer access
            with self._buffer_lock:
                if len(self.experience_buffer) < batch_size:
                    return  # Not enough experience yet
                
                # Convert deque to list for sampling (more efficient than random.sample on deque)
                buffer_list = list(self.experience_buffer)
            
            # Sample random batch from experience buffer
            import random
            batch = random.sample(buffer_list, min(batch_size, len(buffer_list)))
            
            # Thread-safe model update
            with self._model_lock:
                # Prepare training data
                states = torch.FloatTensor([exp['state'] for exp in batch])
                actions = torch.FloatTensor([exp['action'] for exp in batch])
                rewards = torch.FloatTensor([exp['reward'] for exp in batch])
                
                # Forward pass
                predictions = self.model(states).squeeze()
                
                # Calculate loss (reward-weighted BCE)
                # Positive rewards encourage the action taken, negative discourage
                targets = torch.where(rewards > 0, actions, 1 - actions)
                loss = self.criterion(predictions, targets)
                
                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                
                # Gradient clipping to prevent exploding gradients
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                
                self.optimizer.step()
                
                # Update training stats
                self.training_history['episodes'] += 1
                avg_reward = np.mean([exp['reward'] for exp in batch])
                self.training_history['avg_reward_per_episode'] = avg_reward
                self.training_history['last_update'] = datetime.now().isoformat()
                
                logging.debug(f"🧠 RL model updated: Loss={loss.item():.4f}, Avg Reward={avg_reward:.3f}")
            
        except Exception as e:
            logging.error(f"Error updating RL model: {e}")
    
    def save_model(self):
        """Save RL model and training history"""
        try:
            torch.save({
                'model_state_dict': self.model.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'training_history': self.training_history,
                'execution_threshold': self.execution_threshold,
                'save_timestamp': datetime.now().isoformat()
            }, self.model_path)
            
            logging.debug(f"💾 RL model saved: {self.model_path}")
            
        except Exception as e:
            logging.error(f"Error saving RL model: {e}")
    
    def load_model(self):
        """Load existing RL model if available"""
        try:
            if self.model_path.exists():
                checkpoint = torch.load(self.model_path, map_location='cpu', weights_only=False)
                
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                self.training_history = checkpoint.get('training_history', self.training_history)
                self.execution_threshold = checkpoint.get('execution_threshold', 0.7)
                
                episodes = self.training_history.get('episodes', 0)
                avg_reward = self.training_history.get('avg_reward_per_episode', 0.0)
                
                logging.debug(f"📁 RL model loaded: {episodes} episodes trained, avg reward: {avg_reward:.3f}")
            else:
                logging.debug("🆕 No existing RL model found, starting fresh")
                
        except Exception as e:
            logging.warning(f"Error loading RL model: {e}, starting fresh")
            # Reset to fresh model
            self.model = RLSignalFilter()
            self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
    
    def get_training_stats(self) -> Dict:
        """Get RL training statistics"""
        return {
            'episodes_trained': self.training_history.get('episodes', 0),
            'avg_reward': self.training_history.get('avg_reward_per_episode', 0.0),
            'experience_buffer_size': len(self.experience_buffer),
            'execution_threshold': self.execution_threshold,
            'last_update': self.training_history.get('last_update', 'Never')
        }

def build_market_context(symbol: str, dataframes: Dict) -> Dict:
    """
    Costruisce market context per RL state
    
    Args:
        symbol: Trading symbol
        dataframes: Dict con dataframes per timeframes
        
    Returns:
        Dict: Market context features
    """
    try:
        # Use primary timeframe data (15m)
        primary_tf = list(dataframes.keys())[0] if dataframes else None
        if primary_tf and primary_tf in dataframes:
            df = dataframes[primary_tf]
            last_candle = df.iloc[-1]
            
            # Calculate market context features
            context = {
                # Volatility measure (ATR/price)
                'volatility': last_candle.get('atr', 0.0) / last_candle.get('close', 1.0),
                
                # Volume surge detection (current vs 20-period average)
                'volume_surge': last_candle.get('volume', 0.0) / max(df['volume'].rolling(20).mean().iloc[-1], 1.0),
                
                # Trend strength (ADX)
                'trend_strength': last_candle.get('adx', 25.0),
                
                # RSI position (momentum context)
                'rsi_position': last_candle.get('rsi_fast', 50.0)
            }
        else:
            # Fallback neutral context
            context = {
                'volatility': 0.02,
                'volume_surge': 1.0,
                'trend_strength': 25.0,
                'rsi_position': 50.0
            }
        
        return context
        
    except Exception as e:
        logging.error(f"Error building market context for {symbol}: {e}")
        # Return neutral context on error
        return {
            'volatility': 0.02,
            'volume_surge': 1.0,
            'trend_strength': 25.0,
            'rsi_position': 50.0
        }

# Global RL agent instance
global_rl_agent = RLTrainingManager()
