"""
Display utilities for the trading bot
Contains functions for formatted output, analysis display, and performance reporting
"""

import logging
from termcolor import colored


def calculate_ensemble_confidence(tf_predictions, ensemble_value):
    """
    Calcola come viene determinata la confidence dell'ensemble
    
    Returns: explanation string
    """
    try:
        # Conta i voti per ogni classe
        vote_counts = {}
        for tf, pred in tf_predictions.items():
            vote_counts[pred] = vote_counts.get(pred, 0) + 1
        
        # Trova il segnale vincente
        winning_signal = max(vote_counts.items(), key=lambda x: x[1])[0]
        winning_votes = vote_counts[winning_signal]
        total_votes = sum(vote_counts.values())
        
        # Calcola percentage agreement
        agreement_pct = (winning_votes / total_votes) * 100
        
        signal_names = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
        
        explanation = f"Confidence {ensemble_value:.1%} = {winning_votes}/{total_votes} timeframes agree on {signal_names[winning_signal]} ({agreement_pct:.1f}% consensus)"
        
        return explanation
        
    except Exception as e:
        return f"Confidence calculation error: {e}"


def display_symbol_decision_analysis(symbol, signal_data, rl_available=False, risk_manager_available=False):
    """
    Display structured decision analysis for each symbol
    
    Shows the complete decision pipeline: Consensus -> ML -> RL -> Risk Manager -> Final Decision
    """
    try:
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        print(colored(f"\n🔍 {symbol_short} Analysis:", "cyan", attrs=['bold']))
        
        # 1. CONSENSUS TIMEFRAME ANALYSIS
        tf_predictions = signal_data.get('tf_predictions', {})
        if tf_predictions:
            tf_details = []
            signal_names = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
            for tf, pred in tf_predictions.items():
                signal_name = signal_names.get(pred, 'UNKNOWN')
                color = 'red' if signal_name == 'SELL' else 'green' if signal_name == 'BUY' else 'yellow'
                tf_details.append(colored(f"{tf}={signal_name}", color))
            
            # Calculate consensus percentage
            signal_counts = {}
            for pred in tf_predictions.values():
                signal_name = signal_names.get(pred, 'UNKNOWN')
                signal_counts[signal_name] = signal_counts.get(signal_name, 0) + 1
            
            winning_signal = max(signal_counts.items(), key=lambda x: x[1])[0]
            consensus_pct = (signal_counts[winning_signal] / len(tf_predictions)) * 100
            
            consensus_color = 'green' if consensus_pct >= 66 else 'yellow' if consensus_pct >= 50 else 'red'
            print(f"  📊 Consensus: {', '.join(tf_details)} → {colored(f'{consensus_pct:.0f}% agreement', consensus_color)}")
        
        # 2. ML CONFIDENCE
        ml_confidence = signal_data.get('confidence', 0)
        confidence_color = 'green' if ml_confidence >= 0.7 else 'yellow' if ml_confidence >= 0.5 else 'red'
        print(f"  🧠 ML Confidence: {colored(f'{ml_confidence:.1%}', confidence_color)}")
        
        # 3. RL APPROVAL WITH DETAILED REASONING
        if rl_available:
            rl_details = signal_data.get('rl_details', {})
            rl_approved = signal_data.get('rl_approved', False)
            rl_confidence = signal_data.get('rl_confidence', 0)
            
            if rl_approved:
                rl_color = 'green' if rl_confidence >= 0.6 else 'yellow'
                print(f"  🤖 RL Approval: {colored('✅ APPROVED', 'green')} (RL confidence: {colored(f'{rl_confidence:.1%}', rl_color)})")
                
                # Show approval reasons
                if rl_details.get('approvals'):
                    for approval in rl_details['approvals'][:2]:  # Show top 2 reasons
                        print(colored(f"      ✅ {approval}", 'green'))
            else:
                print(f"  🤖 RL Approval: {colored('❌ REJECTED', 'red')}")
                
                # Show detailed rejection reasons
                factors = rl_details.get('factors', {})
                issues = rl_details.get('issues', [])
                
                # Show key factors that caused rejection
                for factor_name, factor_info in factors.items():
                    if factor_info.get('status') in ['TOO_HIGH', 'TOO_LOW', 'WEAK', 'LOW']:
                        status_color = 'red' if factor_info['status'] in ['TOO_HIGH', 'TOO_LOW'] else 'yellow'
                        factor_display = factor_name.replace('_', ' ').title()
                        print(colored(f"      ❌ {factor_display}: {factor_info['value']} (limit: {factor_info['threshold']})", status_color))
                
                # Primary reason
                primary_reason = rl_details.get('primary_reason', 'Unknown reason')
                print(colored(f"      🔒 Primary: {primary_reason}", 'red'))
        else:
            print(f"  🤖 RL Approval: {colored('⚪ N/A', 'white')} (RL system not available)")
        
        # 4. RISK MANAGER VALIDATION
        if risk_manager_available:
            print(f"  🛡️ Risk Manager: {colored('✅ APPROVED', 'green')} (position size validated)")
        else:
            print(f"  🛡️ Risk Manager: {colored('⚪ FALLBACK', 'yellow')} (using conservative sizing)")
        
        # 5. FINAL DECISION
        final_action = signal_data.get('signal_name', 'SKIP')
        if final_action in ['BUY', 'SELL']:
            action_color = 'green'
            action_symbol = '🎯'
        else:
            action_color = 'red'
            action_symbol = '⏭️'
            final_action = 'SKIP'
        
        print(f"  {action_symbol} {colored('DECISION:', 'white', attrs=['bold'])} {colored(f'{final_action}', action_color, attrs=['bold'])}")
        
    except Exception as e:
        logging.error(f"Error displaying decision analysis for {symbol}: {e}")
        print(colored(f"  ❌ Analysis Error: {str(e)[:50]}...", "red"))


def show_performance_summary(cycle_total_time, data_fetch_time=None, ml_time=None, top_symbols_count=0, 
                           timeframes_count=0, complete_symbols_count=0, database_available=False):
    """
    Display cycle performance summary with optimization results
    """
    logging.info(colored("🏆 CYCLE PERFORMANCE SUMMARY", "cyan", attrs=['bold']))
    logging.info(colored("-" * 80, "cyan"))
    
    if data_fetch_time is not None:
        logging.info(colored(f"📊 Data Fetching: {data_fetch_time:.1f}s (Cache-optimized: {top_symbols_count} symbols × {timeframes_count} TF)", "green"))
    
    if ml_time is not None:
        logging.info(colored(f"🧠 ML Predictions: {ml_time:.1f}s (Parallel: {complete_symbols_count} symbols)", "green"))
    
    # Display database performance if available
    if database_available:
        try:
            from core.database_cache import global_db_cache
            db_stats = global_db_cache.get_cache_stats()
            logging.info(colored(f"🗄️ Database Performance: {db_stats['hit_rate_pct']:.1f}% hit rate, {db_stats['total_api_calls_saved']} API calls saved", "green"))
        except Exception as db_error:
            logging.warning(f"Database stats error: {db_error}")
    
    logging.info(colored(f"🚀 Total Cycle: {cycle_total_time:.1f}s", "yellow"))
    
    if top_symbols_count > 0 and timeframes_count > 0:
        efficiency = (top_symbols_count * timeframes_count) / cycle_total_time
        logging.info(colored(f"⚡ Efficiency: {efficiency:.1f} predictions/second", "yellow"))
        
        # Show estimated speedup compared to sequential approach
        estimated_sequential_time = top_symbols_count * timeframes_count * 2  # ~2s per symbol/timeframe sequential
        speedup_factor = estimated_sequential_time / cycle_total_time if cycle_total_time > 0 else 1
        logging.info(colored(f"📈 Estimated speedup: {speedup_factor:.1f}x vs sequential approach", "green"))
    
    logging.info(colored("-" * 80, "cyan"))


def display_data_download_summary(successful_downloads, total_symbols, data_fetch_time):
    """
    Display data download summary with clean formatting
    """
    print(colored("=" * 120, "yellow"))
    print(colored(f"📊 DATA DOWNLOAD SUMMARY", "cyan", attrs=['bold']))
    if total_symbols > 0:
        success_rate = (successful_downloads / total_symbols) * 100
        print(colored(f"✅ Successful downloads: {successful_downloads}/{total_symbols} ({success_rate:.1f}%)", "green"))
        print(colored(f"⏱️ Total download time: {data_fetch_time:.1f}s", "green"))
        print(colored(f"⚡ Average time per symbol: {data_fetch_time/total_symbols:.1f}s", "green"))
    else:
        print(colored(f"❌ No symbols found for analysis!", "red"))
        print(colored(f"⏱️ Total time: {data_fetch_time:.1f}s", "yellow"))
    print(colored("=" * 120, "yellow"))


def display_top_signals(all_signals, limit=10):
    """
    Display top signals ranked by confidence
    """
    if not all_signals:
        logging.warning(colored("⚠️ No signals found this cycle", "yellow"))
        return
        
    logging.info(colored("🏆 TOP SIGNALS BY CONFIDENCE:", "yellow", attrs=['bold']))
    print(colored("-" * 120, "yellow"))
    print(colored(f"{'RANK':<4} {'SYMBOL':<20} {'SIGNAL':<6} {'CONFIDENCE':<12} {'EXPLANATION':<60} {'PRICE':<12}", "white", attrs=['bold']))
    print(colored("-" * 120, "yellow"))
    
    for i, signal in enumerate(all_signals[:limit], 1):
        symbol_short = signal['symbol'].replace('/USDT:USDT', '')
        signal_color = 'green' if signal['signal_name'] == 'BUY' else 'red'
        
        confidence_pct = f"{signal['confidence']:.1%}"
        print(f"{i:<4} {symbol_short:<20} {colored(signal['signal_name'], signal_color, attrs=['bold']):<6} {confidence_pct:<12} {signal['confidence_explanation']:<60} ${signal['price']:.6f}")
    
    print(colored("-" * 120, "yellow"))


def display_selected_symbols(symbols_list, title="SIMBOLI SELEZIONATI", volumes_data=None):
    """
    Display selected symbols in a formatted table with real volumes
    """
    logging.info(colored(f"\n📊 {title} ({len(symbols_list)} totali)", "cyan", attrs=['bold']))
    print(colored("=" * 100, "cyan"))
    print(colored(f"{'RANK':<6} {'SYMBOL':<25} {'VOLUME (24h)':<20} {'NOTES':<35}", "white", attrs=['bold']))
    print(colored("-" * 100, "cyan"))
    
    for i, symbol in enumerate(symbols_list, 1):
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        # Mostra volume reale se disponibile
        if volumes_data and symbol in volumes_data:
            volume = volumes_data[symbol]
            if volume >= 1_000_000_000:  # Miliardi
                volume_text = f"${volume/1_000_000_000:.1f}B"
            elif volume >= 1_000_000:   # Milioni
                volume_text = f"${volume/1_000_000:.0f}M"
            else:
                volume_text = f"${volume:,.0f}"
        else:
            volume_text = "Trading Volume"
        
        print(f"{i:<6} {colored(symbol_short, 'green'):<25} {volume_text:<20} {'Selected for analysis':<35}")
        
        # Add separator every 10 symbols for readability
        if i % 10 == 0 and i < len(symbols_list):
            print(colored("─" * 100, "blue"))
    
    print(colored("=" * 100, "cyan"))
    print(colored(f"✅ ACTIVE: {len(symbols_list)} symbols will be analyzed each cycle", "green", attrs=['bold']))
    print(colored(f"🔄 REFRESH: Symbol ranking updates every trading cycle\n", "yellow"))
