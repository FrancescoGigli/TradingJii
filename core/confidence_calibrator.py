"""
🎯 CONFIDENCE CALIBRATION SYSTEM

Sistema di calibrazione delle confidence basato su risultati reali di backtest.
Converte confidence "raw" (output modello) in confidence "calibrata" (win rate reale).

FUNZIONAMENTO:
1. Backtest storico traccia: confidence raw → risultato trade (WIN/LOSS)
2. Analisi statistica: raggruppa per range confidence → calcola win rate reale
3. Calibration table: mapping da confidence raw a win rate verificato
4. Live trading: confidence raw passa attraverso calibration layer

ESEMPIO:
- XGBoost dice: 95% confidence
- Lookup: range [0.90-1.00] ha 73% win rate storico
- Output calibrato: 73% confidence (più realistica!)
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

_LOG = logging.getLogger(__name__)


class ConfidenceCalibrator:
    """
    Sistema di calibrazione confidence basato su risultati storici
    """
    
    def __init__(self, calibration_file: str = "confidence_calibration.json"):
        self.calibration_file = Path(calibration_file)
        self.calibration_data = {}
        self.is_calibrated = False
        
        # Carica calibrazione esistente se disponibile
        self.load_calibration()
    
    def load_calibration(self) -> bool:
        """Carica calibration table da file"""
        try:
            if self.calibration_file.exists():
                with open(self.calibration_file, 'r') as f:
                    self.calibration_data = json.load(f)
                
                self.is_calibrated = True
                
                # Log info calibrazione
                metadata = self.calibration_data.get('metadata', {})
                _LOG.info(f"📊 Calibrazione caricata:")
                _LOG.info(f"   Data creazione: {metadata.get('created', 'Unknown')}")
                _LOG.info(f"   Trade analizzati: {metadata.get('total_trades', 0)}")
                _LOG.info(f"   Periodo: {metadata.get('backtest_period', 'Unknown')}")
                
                return True
            else:
                _LOG.info("📝 Nessuna calibrazione trovata, usando confidence raw")
                return False
                
        except Exception as e:
            _LOG.error(f"❌ Errore caricamento calibrazione: {e}")
            self.is_calibrated = False
            return False
    
    def calibrate_xgb_confidence(self, raw_confidence: float) -> float:
        """
        Calibra confidence XGBoost usando lookup table
        
        Args:
            raw_confidence: Confidence raw da XGBoost (0.0-1.0)
            
        Returns:
            float: Confidence calibrata basata su win rate storico
        """
        if not self.is_calibrated:
            return raw_confidence  # Fallback: usa confidence raw
        
        try:
            xgb_calibration = self.calibration_data.get('xgb_calibration', [])
            
            # Trova range appropriato
            for range_data in xgb_calibration:
                min_val = range_data['raw_range'][0]
                max_val = range_data['raw_range'][1]
                
                if min_val <= raw_confidence < max_val:
                    calibrated = range_data['calibrated_value']
                    
                    _LOG.debug(
                        f"🎯 XGBoost calibration: {raw_confidence:.1%} → {calibrated:.1%} "
                        f"(based on {range_data['samples']} historical trades)"
                    )
                    
                    return calibrated
            
            # Fallback se non trova range
            _LOG.warning(f"⚠️ No calibration range found for {raw_confidence:.1%}")
            return raw_confidence
            
        except Exception as e:
            _LOG.error(f"❌ Errore calibrazione XGBoost: {e}")
            return raw_confidence
    
    def calibrate_rl_confidence(self, raw_confidence: float) -> float:
        """
        Calibra confidence RL usando lookup table
        
        Args:
            raw_confidence: Confidence raw da RL (0.0-1.0)
            
        Returns:
            float: Confidence calibrata basata su win rate storico
        """
        if not self.is_calibrated:
            return raw_confidence  # Fallback: usa confidence raw
        
        try:
            rl_calibration = self.calibration_data.get('rl_calibration', [])
            
            # Trova range appropriato
            for range_data in rl_calibration:
                min_val = range_data['raw_range'][0]
                max_val = range_data['raw_range'][1]
                
                if min_val <= raw_confidence < max_val:
                    calibrated = range_data['calibrated_value']
                    
                    _LOG.debug(
                        f"🤖 RL calibration: {raw_confidence:.1%} → {calibrated:.1%} "
                        f"(based on {range_data['samples']} historical trades)"
                    )
                    
                    return calibrated
            
            # Fallback se non trova range
            _LOG.warning(f"⚠️ No calibration range found for {raw_confidence:.1%}")
            return raw_confidence
            
        except Exception as e:
            _LOG.error(f"❌ Errore calibrazione RL: {e}")
            return raw_confidence
    
    def get_calibration_stats(self) -> Dict:
        """Ottieni statistiche calibrazione"""
        if not self.is_calibrated:
            return {
                'calibrated': False,
                'message': 'No calibration loaded'
            }
        
        metadata = self.calibration_data.get('metadata', {})
        xgb_ranges = len(self.calibration_data.get('xgb_calibration', []))
        rl_ranges = len(self.calibration_data.get('rl_calibration', []))
        
        return {
            'calibrated': True,
            'created': metadata.get('created', 'Unknown'),
            'total_trades': metadata.get('total_trades', 0),
            'backtest_period': metadata.get('backtest_period', 'Unknown'),
            'xgb_ranges': xgb_ranges,
            'rl_ranges': rl_ranges,
            'stop_loss': metadata.get('stop_loss', 'Unknown'),
            'trailing_trigger': metadata.get('trailing_trigger', 'Unknown')
        }


class CalibrationAnalyzer:
    """
    Analizza risultati backtest e genera tabella calibrazione
    """
    
    def __init__(self):
        self.trades: List[Dict] = []
    
    def add_trade(self, trade_data: Dict):
        """Aggiungi trade result per analisi"""
        self.trades.append(trade_data)
    
    def analyze_and_generate_calibration(
        self, 
        output_file: str = "confidence_calibration.json",
        ranges: List[Tuple[float, float]] = None
    ) -> Dict:
        """
        Analizza trades e genera calibration table
        
        Args:
            output_file: File output per calibration table
            ranges: Custom ranges (default: [0.9-1.0, 0.8-0.9, 0.7-0.8, 0.6-0.7, 0-0.6])
            
        Returns:
            Dict: Calibration data generated
        """
        if not self.trades:
            _LOG.error("❌ Nessun trade da analizzare")
            return {}
        
        # Default ranges
        if ranges is None:
            ranges = [
                (0.90, 1.00),
                (0.80, 0.90),
                (0.70, 0.80),
                (0.60, 0.70),
                (0.00, 0.60)
            ]
        
        _LOG.info(f"📊 Analyzing {len(self.trades)} trades for calibration...")
        
        # Analizza XGBoost confidence
        xgb_calibration = self._analyze_confidence_ranges(
            confidence_key='xgb_confidence',
            ranges=ranges
        )
        
        # Analizza RL confidence
        rl_calibration = self._analyze_confidence_ranges(
            confidence_key='rl_confidence',
            ranges=ranges
        )
        
        # Metadata
        metadata = {
            'created': datetime.now().isoformat(),
            'total_trades': len(self.trades),
            'backtest_period': self._get_date_range(),
            'stop_loss': self._get_config_value('stop_loss'),
            'trailing_trigger': self._get_config_value('trailing_trigger'),
            'trailing_distance': self._get_config_value('trailing_distance')
        }
        
        # Componi calibration data
        calibration_data = {
            'metadata': metadata,
            'xgb_calibration': xgb_calibration,
            'rl_calibration': rl_calibration
        }
        
        # Salva su file
        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(calibration_data, f, indent=2)
        
        _LOG.info(f"✅ Calibration table saved: {output_path}")
        
        # Log summary
        self._log_calibration_summary(calibration_data)
        
        return calibration_data
    
    def _analyze_confidence_ranges(
        self, 
        confidence_key: str,
        ranges: List[Tuple[float, float]]
    ) -> List[Dict]:
        """Analizza win rate per range confidence"""
        calibration = []
        
        for min_conf, max_conf in ranges:
            # Filtra trades in questo range
            range_trades = [
                t for t in self.trades
                if t.get(confidence_key) is not None
                and min_conf <= t[confidence_key] < max_conf
            ]
            
            if not range_trades:
                continue
            
            # Calcola win rate
            wins = sum(1 for t in range_trades if t.get('result') == 'WIN')
            total = len(range_trades)
            win_rate = wins / total if total > 0 else 0.0
            
            # Calcola avg PnL
            avg_pnl = np.mean([t.get('pnl_pct', 0.0) for t in range_trades])
            
            calibration.append({
                'raw_range': [min_conf, max_conf],
                'calibrated_value': round(win_rate, 3),
                'samples': total,
                'wins': wins,
                'losses': total - wins,
                'avg_pnl_pct': round(avg_pnl, 2),
                'sample_trades': [
                    {
                        'symbol': t.get('symbol', 'Unknown'),
                        'confidence': round(t.get(confidence_key, 0.0), 3),
                        'result': t.get('result', 'Unknown'),
                        'pnl_pct': round(t.get('pnl_pct', 0.0), 2)
                    }
                    for t in range_trades[:5]  # Prime 5 come esempio
                ]
            })
        
        return calibration
    
    def _get_date_range(self) -> str:
        """Ottieni range date da trades"""
        if not self.trades:
            return "Unknown"
        
        dates = [t.get('entry_date') for t in self.trades if t.get('entry_date')]
        if not dates:
            return "Unknown"
        
        try:
            dates_sorted = sorted(dates)
            return f"{dates_sorted[0]} to {dates_sorted[-1]}"
        except:
            return "Unknown"
    
    def _get_config_value(self, key: str) -> any:
        """Ottieni valore config da trades se disponibile"""
        for trade in self.trades:
            if key in trade:
                return trade[key]
        return "Unknown"
    
    def _log_calibration_summary(self, calibration_data: Dict):
        """Log summary della calibrazione generata"""
        _LOG.info("=" * 80)
        _LOG.info("📊 CALIBRATION SUMMARY")
        _LOG.info("=" * 80)
        
        # XGBoost
        _LOG.info("\n🎯 XGBoost Calibration:")
        for range_data in calibration_data['xgb_calibration']:
            min_val, max_val = range_data['raw_range']
            calibrated = range_data['calibrated_value']
            samples = range_data['samples']
            wins = range_data['wins']
            losses = range_data['losses']
            
            _LOG.info(
                f"  Range [{min_val:.0%}-{max_val:.0%}]: "
                f"{calibrated:.1%} win rate "
                f"({wins}W/{losses}L from {samples} trades)"
            )
        
        # RL
        _LOG.info("\n🤖 RL Calibration:")
        for range_data in calibration_data['rl_calibration']:
            min_val, max_val = range_data['raw_range']
            calibrated = range_data['calibrated_value']
            samples = range_data['samples']
            wins = range_data['wins']
            losses = range_data['losses']
            
            _LOG.info(
                f"  Range [{min_val:.0%}-{max_val:.0%}]: "
                f"{calibrated:.1%} win rate "
                f"({wins}W/{losses}L from {samples} trades)"
            )
        
        _LOG.info("=" * 80)


# Global calibrator instance
global_calibrator = ConfidenceCalibrator()
