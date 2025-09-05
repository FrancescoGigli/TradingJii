"""
🚀 PARALLEL ML PREDICTION OPTIMIZATION

Sistema di predizioni ML parallele per massimizzare la velocità di inferenza
mantenendo la stessa logica di business e gli stessi numeri di simboli.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import numpy as np
from termcolor import colored

from predictor import predict_signal_ensemble
import config

class ParallelMLPredictor:
    """
    Gestore delle predizioni ML parallele con ottimizzazione performance
    """
    
    def __init__(self, max_workers=None):
        """
        Args:
            max_workers: Numero massimo di workers per ThreadPool
                        Se None, usa cpu_count()
        """
        self.max_workers = max_workers or min(cpu_count(), 8)  # Max 8 workers per stabilità

    async def predict_all_symbols_parallel(self, symbol_data_dict, xgb_models, xgb_scalers, time_steps):
        """
        🚀 PARALLEL PREDICTION per tutti i simboli
        
        Esegue predizioni ML su tutti i simboli simultaneamente usando ThreadPoolExecutor.
        Mantiene la stessa logica di predict_signal_ensemble ma in parallelo.
        
        Args:
            symbol_data_dict: {symbol: {timeframe: dataframe}}
            xgb_models: Dict dei modelli caricati
            xgb_scalers: Dict degli scalers
            time_steps: Time steps per predizioni
            
        Returns:
            dict: {symbol: (ensemble_value, final_signal, tf_predictions)}
        """
        start_time = time.time()
        
        # Prepara tutti i task di predizione
        symbols_with_data = [symbol for symbol, dataframes in symbol_data_dict.items() 
                            if len(dataframes) == len(config.ENABLED_TIMEFRAMES)]
        
        total_symbols = len(symbols_with_data)
        
        logging.info(f"🧠 Starting parallel ML predictions for {total_symbols} symbols")
        logging.info(f"⚡ Using {self.max_workers} parallel workers")
        
        # ThreadPoolExecutor per CPU-intensive ML predictions
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submetti tutti i task
            future_to_symbol = {}
            
            for symbol in symbols_with_data:
                dataframes = symbol_data_dict[symbol]
                
                # Sottometti task asincrono
                future = executor.submit(
                    predict_signal_ensemble, 
                    dataframes, xgb_models, xgb_scalers, symbol, time_steps
                )
                future_to_symbol[future] = symbol
            
            # Raccogli risultati man mano che completano
            prediction_results = {}
            completed_count = 0
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                
                try:
                    ensemble_value, final_signal, tf_predictions = future.result(timeout=30)  # 30s timeout per predizione
                    prediction_results[symbol] = (ensemble_value, final_signal, tf_predictions)
                    
                    completed_count += 1
                    progress_pct = (completed_count / total_symbols) * 100
                    
                    # Log progresso ogni 10% o per segnali validi
                    if (completed_count % max(1, total_symbols // 10) == 0 or 
                        completed_count == total_symbols or 
                        (ensemble_value is not None and final_signal is not None and final_signal != 2)):
                        
                        elapsed = time.time() - start_time
                        rate = completed_count / elapsed if elapsed > 0 else 0
                        eta = (total_symbols - completed_count) / rate if rate > 0 else 0
                        
                        signal_info = ""
                        if ensemble_value is not None and final_signal is not None and final_signal != 2:
                            signal_name = 'BUY' if final_signal == 1 else 'SELL'
                            signal_info = f" | 🎯 {signal_name} ({ensemble_value:.1%})"
                        
                        logging.info(f"🧠 ML Progress: {completed_count}/{total_symbols} ({progress_pct:.1f}%) | Rate: {rate:.1f}/s | ETA: {eta:.0f}s{signal_info}")
                
                except Exception as e:
                    logging.error(f"❌ Prediction failed for {symbol}: {e}")
                    prediction_results[symbol] = (None, None, {})
                    completed_count += 1

        # Performance summary
        total_time = time.time() - start_time
        successful_predictions = sum(1 for result in prediction_results.values() 
                                   if result[0] is not None)
        
        logging.info(f"🎉 Parallel ML predictions complete!")
        logging.info(f"   ✅ Successful: {successful_predictions}/{total_symbols} ({successful_predictions/total_symbols*100:.1f}%)")
        logging.info(f"   ⏱️ Total time: {total_time:.1f}s")
        logging.info(f"   🚀 Avg prediction time: {total_time/total_symbols:.2f}s per symbol")
        
        return prediction_results

    async def predict_batch_symbols(self, symbol_batch, symbol_data_dict, xgb_models, xgb_scalers, time_steps):
        """
        🚀 BATCH PREDICTION per un subset di simboli
        
        Utile per processare simboli in gruppi più piccoli se si preferisce
        un approccio più controllato rispetto al parallelismo totale.
        
        Args:
            symbol_batch: Lista di simboli da processare in questo batch
            symbol_data_dict: Dati completi di tutti i simboli
            xgb_models, xgb_scalers, time_steps: Parametri ML
            
        Returns:
            dict: Risultati delle predizioni per questo batch
        """
        batch_size = len(symbol_batch)
        logging.info(f"🧠 Processing batch of {batch_size} symbols")
        
        # Usa meno workers per batch più piccoli
        batch_workers = min(self.max_workers, batch_size)
        
        with ThreadPoolExecutor(max_workers=batch_workers) as executor:
            future_to_symbol = {}
            
            for symbol in symbol_batch:
                if symbol in symbol_data_dict:
                    dataframes = symbol_data_dict[symbol]
                    future = executor.submit(
                        predict_signal_ensemble,
                        dataframes, xgb_models, xgb_scalers, symbol, time_steps
                    )
                    future_to_symbol[future] = symbol
            
            # Raccogli risultati
            batch_results = {}
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result(timeout=15)  # Timeout più breve per batch
                    batch_results[symbol] = result
                except Exception as e:
                    logging.error(f"❌ Batch prediction failed for {symbol}: {e}")
                    batch_results[symbol] = (None, None, {})
        
        return batch_results

# ==============================================================================
# PARALLEL PROCESSING UTILITIES
# ==============================================================================

async def process_symbols_in_batches(symbols, batch_size, symbol_data_dict, 
                                   xgb_models, xgb_scalers, time_steps):
    """
    🔄 BATCH PROCESSING alternativo per simboli
    
    Processa simboli in batch sequenziali ma con parallelismo interno a ogni batch.
    Utile per gestire meglio la memoria e il rate limiting.
    
    Args:
        symbols: Lista completa simboli
        batch_size: Dimensione di ogni batch
        Altri parametri: Come predict_all_symbols_parallel
        
    Returns:
        dict: Risultati aggregati di tutti i batch
    """
    predictor = ParallelMLPredictor()
    all_results = {}
    
    # Dividi simboli in batch
    symbol_batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
    
    logging.info(f"📦 Processing {len(symbols)} symbols in {len(symbol_batches)} batches of {batch_size}")
    
    for batch_idx, batch in enumerate(symbol_batches, 1):
        logging.info(f"📦 Processing batch {batch_idx}/{len(symbol_batches)}: {len(batch)} symbols")
        
        batch_results = await predictor.predict_batch_symbols(
            batch, symbol_data_dict, xgb_models, xgb_scalers, time_steps
        )
        
        all_results.update(batch_results)
        
        # Piccola pausa tra batch per stabilità
        if batch_idx < len(symbol_batches):
            await asyncio.sleep(0.1)
    
    return all_results

# ==============================================================================
# GLOBAL PARALLEL PREDICTOR INSTANCE
# ==============================================================================

# Istanza globale del predictor parallelo
global_parallel_predictor = ParallelMLPredictor()

async def predict_all_parallel(symbol_data_dict, xgb_models, xgb_scalers, time_steps):
    """
    🚀 WRAPPER FUNCTION per predizioni parallele
    
    Interfaccia semplificata per l'uso in main.py
    """
    return await global_parallel_predictor.predict_all_symbols_parallel(
        symbol_data_dict, xgb_models, xgb_scalers, time_steps
    )
