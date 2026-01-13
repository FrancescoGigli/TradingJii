"""
🤖 ML Inference Agent - Main Entry Point

Runs inference on all symbols periodically and saves to database.
"""

import time
import logging
import sys
from datetime import datetime

from config import (
    INFERENCE_INTERVAL, 
    INFERENCE_TIMEFRAME, 
    CANDLES_FOR_FEATURES,
    LOG_LEVEL
)
from core.database import (
    init_ml_signals_table,
    get_available_symbols,
    get_ohlcv_data,
    save_ml_signals_batch,
    cleanup_old_signals
)
from core.predictor import MLPredictor

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def run_inference_cycle(predictor: MLPredictor, timeframe: str):
    """Run one inference cycle for all symbols"""
    
    logger.info(f"🔄 Starting inference cycle for timeframe: {timeframe}")
    start_time = time.time()
    
    # Get available symbols
    symbols = get_available_symbols(timeframe)
    logger.info(f"📊 Found {len(symbols)} symbols with data")
    
    if not symbols:
        logger.warning("No symbols found in database")
        return
    
    # Collect data for all symbols
    symbols_data = {}
    for symbol in symbols:
        df = get_ohlcv_data(symbol, timeframe, CANDLES_FOR_FEATURES)
        if df is not None and len(df) >= 50:
            symbols_data[symbol] = df
    
    logger.info(f"📈 Loaded data for {len(symbols_data)} symbols")
    
    if not symbols_data:
        logger.warning("No valid data for any symbol")
        return
    
    # Run predictions
    predictions = []
    for symbol, df in symbols_data.items():
        try:
            pred = predictor.predict(df)
            if pred:
                pred['symbol'] = symbol
                pred['timeframe'] = timeframe
                predictions.append(pred)
        except Exception as e:
            logger.error(f"Error predicting {symbol}: {e}")
    
    # Save to database
    if predictions:
        save_ml_signals_batch(predictions)
        
        # Log summary
        buy_long = sum(1 for p in predictions if p['signal_long'] == 'BUY')
        buy_short = sum(1 for p in predictions if p['signal_short'] == 'BUY')
        
        logger.info(f"✅ Inference complete:")
        logger.info(f"   Predictions: {len(predictions)}")
        logger.info(f"   LONG BUY signals: {buy_long}")
        logger.info(f"   SHORT BUY signals: {buy_short}")
        
        # Top opportunities
        sorted_long = sorted(predictions, key=lambda x: x['confidence_long'], reverse=True)[:3]
        sorted_short = sorted(predictions, key=lambda x: x['confidence_short'], reverse=True)[:3]
        
        logger.info("🏆 Top LONG opportunities:")
        for p in sorted_long:
            logger.info(f"   {p['symbol']}: confidence={p['confidence_long']:.1f}")
        
        logger.info("🏆 Top SHORT opportunities:")
        for p in sorted_short:
            logger.info(f"   {p['symbol']}: confidence={p['confidence_short']:.1f}")
    
    elapsed = time.time() - start_time
    logger.info(f"⏱️ Inference cycle completed in {elapsed:.2f}s")


def main():
    """Main entry point"""
    
    logger.info("=" * 60)
    logger.info("🤖 ML INFERENCE AGENT STARTING")
    logger.info("=" * 60)
    logger.info(f"   Inference interval: {INFERENCE_INTERVAL}s ({INFERENCE_INTERVAL//60} min)")
    logger.info(f"   Timeframe: {INFERENCE_TIMEFRAME}")
    logger.info("=" * 60)
    
    # Initialize database table
    init_ml_signals_table()
    
    # Initialize predictor
    predictor = MLPredictor()
    
    # Load models
    if not predictor.load_models("latest"):
        logger.error("❌ Failed to load models. Exiting.")
        sys.exit(1)
    
    # Main loop
    cycle_count = 0
    while True:
        try:
            cycle_count += 1
            logger.info(f"\n{'='*40}")
            logger.info(f"📍 Cycle #{cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*40}")
            
            # Run inference
            run_inference_cycle(predictor, INFERENCE_TIMEFRAME)
            
            # Cleanup old signals periodically
            if cycle_count % 12 == 0:  # Every hour (if interval is 5 min)
                cleanup_old_signals(days=7)
            
            # Wait for next cycle
            logger.info(f"💤 Sleeping for {INFERENCE_INTERVAL}s until next cycle...")
            time.sleep(INFERENCE_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("👋 Received shutdown signal. Exiting...")
            break
        except Exception as e:
            logger.error(f"❌ Error in inference cycle: {e}")
            logger.info("⏳ Waiting 60s before retry...")
            time.sleep(60)


if __name__ == "__main__":
    main()
