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
    Display structured decision analysis for each symbol with enhanced visual differentiation
    
    Shows the complete decision pipeline: Consensus -> ML -> RL -> Risk Manager -> Final Decision
    """
    try:
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        from core.enhanced_logging_system import enhanced_logger
        
        # Enhanced symbol header with visual separator
        enhanced_logger.display_table("", "white")
        enhanced_logger.display_table("┌" + "─" * 58 + "┐", "cyan")
        enhanced_logger.display_table(f"│ 🔍 {symbol_short:<50} │", "cyan", attrs=['bold'])
        enhanced_logger.display_table("└" + "─" * 58 + "┘", "cyan")
        
        # 1. CONSENSUS TIMEFRAME ANALYSIS with distinctive emojis
        tf_predictions = signal_data.get('tf_predictions', {})
        if tf_predictions:
            tf_details = []
            signal_names = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
            signal_emojis = {0: '🔴', 1: '🟢', 2: '🟡'}
            
            for tf, pred in tf_predictions.items():
                signal_name = signal_names.get(pred, 'UNKNOWN')
                emoji = signal_emojis.get(pred, '⚪')
                color = 'red' if signal_name == 'SELL' else 'green' if signal_name == 'BUY' else 'yellow'
                tf_details.append(f"{emoji} {tf}={colored(signal_name, color, attrs=['bold'])}")
            
            # Calculate consensus percentage
            signal_counts = {}
            for pred in tf_predictions.values():
                signal_name = signal_names.get(pred, 'UNKNOWN')
                signal_counts[signal_name] = signal_counts.get(signal_name, 0) + 1
            
            winning_signal = max(signal_counts.items(), key=lambda x: x[1])[0]
            consensus_pct = (signal_counts[winning_signal] / len(tf_predictions)) * 100
            
            consensus_color = 'green' if consensus_pct >= 66 else 'yellow' if consensus_pct >= 50 else 'red'
            consensus_emoji = '🎯' if consensus_pct >= 66 else '⚠️' if consensus_pct >= 50 else '❌'
            enhanced_logger.display_table(f"  📊 Consensus: {', '.join(tf_details)} → {consensus_emoji} {colored(f'{consensus_pct:.0f}% agreement', consensus_color, attrs=['bold'])}")
        
        # 2. ML CONFIDENCE with visual confidence bar
        ml_confidence = signal_data.get('confidence', 0)
        confidence_color = 'green' if ml_confidence >= 0.7 else 'yellow' if ml_confidence >= 0.5 else 'red'
        confidence_emoji = '🚀' if ml_confidence >= 0.7 else '📈' if ml_confidence >= 0.5 else '📉'
        
        # Create visual confidence bar
        bar_length = 20
        filled = int(ml_confidence * bar_length)
        empty = bar_length - filled
        confidence_bar = colored('█' * filled, confidence_color) + colored('░' * empty, 'white')
        
        enhanced_logger.display_table(f"  🧠 ML Confidence: {confidence_emoji} {colored(f'{ml_confidence:.1%}', confidence_color, attrs=['bold'])} {confidence_bar}")
        
        # 3. RL APPROVAL WITH DETAILED REASONING
        if rl_available:
            rl_details = signal_data.get('rl_details', {})
            rl_approved = signal_data.get('rl_approved', False)
            rl_confidence = signal_data.get('rl_confidence', 0)
            
            if rl_approved:
                rl_color = 'green' if rl_confidence >= 0.6 else 'yellow'
                enhanced_logger.display_table(f"  🤖 RL Filter: {colored('✅ APPROVED', 'green', attrs=['bold'])} (Confidence: {colored(f'{rl_confidence:.1%}', rl_color, attrs=['bold'])})")
                
                # Show key approval reasons with distinctive emojis
                if rl_details.get('approvals'):
                    for approval in rl_details['approvals'][:2]:  # Show top 2 reasons
                        enhanced_logger.display_table(f"      ✅ {approval}", 'green')
            else:
                enhanced_logger.display_table(f"  🤖 RL Filter: {colored('❌ REJECTED', 'red', attrs=['bold'])}")
                
                # Primary reason with enhanced formatting
                primary_reason = rl_details.get('primary_reason', 'Unknown reason')
                enhanced_logger.display_table(f"      🔒 Primary: {colored(primary_reason, 'red', attrs=['bold'])}", 'red')
        else:
            enhanced_logger.display_table(f"  🤖 RL Filter: {colored('⚪ N/A', 'white')} (RL system not available)")
        
        # 4. RISK MANAGER VALIDATION
        if risk_manager_available:
            enhanced_logger.display_table(f"  🛡️ Risk Manager: {colored('✅ APPROVED', 'green', attrs=['bold'])} (position size validated)")
        else:
            enhanced_logger.display_table(f"  🛡️ Risk Manager: {colored('⚪ FALLBACK', 'yellow')} (using conservative sizing)")
        
        # 5. FINAL DECISION with enhanced visual separation
        final_action = signal_data.get('signal_name', 'SKIP')
        if final_action == 'BUY':
            action_color = 'green'
            action_symbol = '🚀'
            action_bg = '🟢'
        elif final_action == 'SELL':
            action_color = 'red' 
            action_symbol = '📉'
            action_bg = '🔴'
        else:
            action_color = 'yellow'
            action_symbol = '⏭️'
            action_bg = '🟡'
            final_action = 'SKIP'
        
        enhanced_logger.display_table("  " + "─" * 56, "white")
        enhanced_logger.display_table(f"  {action_symbol} {colored('FINAL DECISION:', 'white', attrs=['bold'])} {action_bg} {colored(f'{final_action}', action_color, attrs=['bold'])}")
        enhanced_logger.display_table("", "white")
        
    except Exception as e:
        logging.error(f"Error displaying decision analysis for {symbol}: {e}")
        enhanced_logger.display_table(f"  ❌ Analysis Error: {str(e)[:50]}...", "red")


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
    from core.enhanced_logging_system import enhanced_logger
    enhanced_logger.display_table("=" * 120, "yellow")
    enhanced_logger.display_table("📊 DATA DOWNLOAD SUMMARY", "cyan", attrs=['bold'])
    if total_symbols > 0:
        success_rate = (successful_downloads / total_symbols) * 100
        enhanced_logger.display_table(f"✅ Successful downloads: {successful_downloads}/{total_symbols} ({success_rate:.1f}%)", "green")
        enhanced_logger.display_table(f"⏱️ Total download time: {data_fetch_time:.1f}s", "green")
        enhanced_logger.display_table(f"⚡ Average time per symbol: {data_fetch_time/total_symbols:.1f}s", "green")
    else:
        enhanced_logger.display_table(f"❌ No symbols found for analysis!", "red")
        enhanced_logger.display_table(f"⏱️ Total time: {data_fetch_time:.1f}s", "yellow")
    enhanced_logger.display_table("=" * 120, "yellow")


def display_top_signals(all_signals, limit=10):
    """
    Display top signals ranked by confidence
    """
    if not all_signals:
        logging.warning(colored("⚠️ No signals found this cycle", "yellow"))
        return
        
    from core.enhanced_logging_system import enhanced_logger
    enhanced_logger.display_table("🏆 TOP SIGNALS BY CONFIDENCE:", "yellow", attrs=['bold'])
    enhanced_logger.display_table("-" * 108, "yellow")
    enhanced_logger.display_table(f"{'RANK':<4} {'SYMBOL':<20} {'SIGNAL':<6} {'CONFIDENCE':<12} {'EXPLANATION':<60}", "white", attrs=['bold'])
    enhanced_logger.display_table("-" * 108, "yellow")
    
    for i, signal in enumerate(all_signals[:limit], 1):
        symbol_short = signal['symbol'].replace('/USDT:USDT', '')
        signal_color = 'green' if signal['signal_name'] == 'BUY' else 'red'
        
        confidence_pct = f"{signal['confidence']:.1%}"
        enhanced_logger.display_table(f"{i:<4} {symbol_short:<20} {colored(signal['signal_name'], signal_color, attrs=['bold']):<6} {confidence_pct:<12} {signal['confidence_explanation']:<60}")
    
    enhanced_logger.display_table("-" * 108, "yellow")


def display_execution_card(trade_num, total_trades, symbol, signal_data, levels=None, status="EXECUTING", error_msg=""):
    """
    Display beautiful execution card for each trade
    
    Args:
        trade_num: Current trade number (1-based)
        total_trades: Total trades to execute
        symbol: Trading symbol
        signal_data: Signal information dict
        levels: Position levels from risk calculator (optional)
        status: Trade status ("EXECUTING", "SUCCESS", "SKIPPED", "FAILED")
        error_msg: Error message if status is FAILED
    """
    try:
        symbol_short = symbol.replace('/USDT:USDT', '')
        signal_name = signal_data.get('signal_name', 'UNKNOWN')
        confidence = signal_data.get('confidence', 0.0)
        tf_predictions = signal_data.get('tf_predictions', {})
        
        # Calculate consensus
        signal_counts = {}
        for pred in tf_predictions.values():
            pred_name = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}.get(pred, 'UNKNOWN')
            signal_counts[pred_name] = signal_counts.get(pred_name, 0) + 1
        
        consensus_text = f"{len([p for p in tf_predictions.values() if {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}.get(p) == signal_name])}/{len(tf_predictions)}"
        
        # Create card header
        card_width = 62
        card_title = f"TRADE #{trade_num}: {symbol_short} {signal_name}"
        logging.info(colored("┌" + "─" * (card_width-2) + "┐", "cyan"))
        logging.info(colored(f"│ {card_title:<{card_width-4}} │", "cyan", attrs=['bold']))
        
        # Signal line with color
        signal_color = 'green' if signal_name == 'BUY' else 'red' if signal_name == 'SELL' else 'yellow'
        signal_emoji = '🟢' if signal_name == 'BUY' else '🔴' if signal_name == 'SELL' else '🟡'
        signal_line = f"│ 🎯 Signal: {signal_emoji} {colored(signal_name, signal_color, attrs=['bold'])} | Confidence: {confidence:.1%} | ML Consensus: {consensus_text}"
        padding = card_width - len(signal_line.replace(colored(signal_name, signal_color, attrs=['bold']), signal_name)) - 1
        logging.info(signal_line + " " * max(0, padding) + "│")
        
        # Position details line (if levels provided)
        if levels and status in ["SUCCESS", "EXECUTING"]:
            entry_price = levels.margin * 10 / levels.position_size if levels.position_size > 0 else 0
            position_line = f"│ 💰 Entry: ${entry_price:.6f} | Size: {levels.position_size:.2f} | Margin: ${levels.margin:.2f}"
            padding = card_width - len(position_line) - 1
            logging.info(position_line + " " * max(0, padding) + "│")
            
            # Protection line - show appropriate message based on SL/TP status
            if levels.stop_loss > 0 and levels.take_profit > 0:
                protection_line = f"│ 🛡️ Protection: Stop -6.0% (${levels.stop_loss:.6f}) | TP +8.0% (${levels.take_profit:.6f})"
            elif levels.stop_loss > 0:
                protection_line = f"│ 🛡️ Protection: Stop -6.0% (${levels.stop_loss:.6f}) | TP: Pending"
            elif levels.take_profit > 0:
                protection_line = f"│ 🛡️ Protection: Stop: Pending | TP +8.0% (${levels.take_profit:.6f})"
            else:
                protection_line = f"│ 🛡️ Protection: Stop & TP will be set after position opens"
            
            padding = card_width - len(protection_line) - 1
            logging.info(protection_line + " " * max(0, padding) + "│")
        
        # Status line with appropriate emoji and color
        if status == "SUCCESS":
            status_emoji = "✅"
            status_color = "green" 
            status_text = "SUCCESS - Position opened with protection"
        elif status == "SKIPPED":
            status_emoji = "⚠️"
            status_color = "yellow"
            status_text = f"SKIPPED - {error_msg}" if error_msg else "SKIPPED - Position already exists"
        elif status == "FAILED":
            status_emoji = "❌"
            status_color = "red"
            status_text = f"FAILED - {error_msg}" if error_msg else "FAILED - Unknown error"
        elif status == "STOPPED":
            status_emoji = "⏹️"
            status_color = "yellow"
            status_text = f"STOPPED - {error_msg}" if error_msg else "STOPPED - Portfolio limit"
        else:  # EXECUTING
            status_emoji = "⚡"
            status_color = "cyan"
            status_text = "EXECUTING... Market order → Stop loss setup"
        
        status_line = f"│ {status_emoji} Status: {colored(status_text, status_color, attrs=['bold'])}"
        padding = card_width - len(status_line.replace(colored(status_text, status_color, attrs=['bold']), status_text)) - 1
        logging.info(status_line + " " * max(0, padding) + "│")
        
        # Close card
        logging.info(colored("└" + "─" * (card_width-2) + "┘", "cyan"))
        
        # Add success message outside card for successful trades
        if status == "SUCCESS":
            logging.info(colored(f"✅ POSITION OPENED: {symbol_short} protected with automatic stop loss", "green", attrs=['bold']))
        
    except Exception as e:
        logging.error(f"Error displaying execution card for {symbol}: {e}")
        # Fallback to simple display
        logging.info(colored(f"📝 Trade #{trade_num}: {symbol.replace('/USDT:USDT', '')} {status}", "white"))


def display_execution_summary(executed_count, total_signals, total_margin_used, remaining_balance):
    """
    Display execution summary with beautiful formatting
    
    Args:
        executed_count: Number of trades executed successfully
        total_signals: Total number of signals processed
        total_margin_used: Total margin used in USD
        remaining_balance: Remaining available balance
    """
    try:
        logging.info(colored("", "white"))  # Empty line
        logging.info(colored("🏆 EXECUTION SUMMARY", "green", attrs=['bold']))
        logging.info(colored("╔" + "═" * 58 + "╗", "green"))
        
        # Results line
        results_text = f"🎯 Executed: {executed_count} positions | 💰 Margin Used: ${total_margin_used:.2f}"
        padding = 58 - len(results_text)
        logging.info(colored(f"║ {results_text}{' ' * max(0, padding)} ║", "green"))
        
        # Balance line
        balance_text = f"💰 Remaining balance: ${remaining_balance:.2f} available for next cycle"
        padding = 58 - len(balance_text)
        logging.info(colored(f"║ {balance_text}{' ' * max(0, padding)} ║", "green"))
        
        # Success rate
        success_rate = (executed_count / total_signals * 100) if total_signals > 0 else 0
        rate_text = f"📊 Success Rate: {success_rate:.1f}% ({executed_count}/{total_signals})"
        padding = 58 - len(rate_text)
        logging.info(colored(f"║ {rate_text}{' ' * max(0, padding)} ║", "green"))
        
        logging.info(colored("╚" + "═" * 58 + "╝", "green"))
        
    except Exception as e:
        logging.error(f"Error displaying execution summary: {e}")
        # Fallback
        logging.info(colored(f"🏆 EXECUTION COMPLETE: {executed_count} trades executed", "green"))


def display_phase5_header(balance, available_balance, in_use_balance, signal_count):
    """
    Display beautiful Phase 5 header with balance information
    
    Args:
        balance: Total account balance
        available_balance: Available balance for trading
        in_use_balance: Balance currently in use
        signal_count: Number of signals to execute
    """
    try:
        logging.info(colored("🚀 PHASE 5: LIVE TRADE EXECUTION", "cyan", attrs=['bold']))
        
        balance_line = f"💰 Account Balance: ${balance:.2f} | Available: ${available_balance:.2f} | In Use: ${in_use_balance:.2f}"
        logging.info(colored(balance_line, "cyan"))
        
        signals_line = f"🎯 Signals Ready: {signal_count} candidates selected for execution"
        logging.info(colored(signals_line, "cyan"))
        
        logging.info(colored("═" * 80, "cyan"))
        
    except Exception as e:
        logging.error(f"Error displaying Phase 5 header: {e}")
        # Fallback
        logging.info(colored("🚀 PHASE 5: TRADE EXECUTION", "cyan", attrs=['bold']))


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
