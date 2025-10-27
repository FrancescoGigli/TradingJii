#!/usr/bin/env python3
"""
📊 CALIBRATION RESULTS VISUALIZER

Script per visualizzare i risultati della calibrazione in modo grafico.

UTILIZZO:
    python visualize_calibration.py
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from termcolor import colored

def load_calibration_data(file_path="confidence_calibration.json"):
    """Carica dati calibrazione"""
    if not Path(file_path).exists():
        print(colored(f"❌ File {file_path} not found!", "red"))
        print(colored("   Run: python backtest_calibration.py first", "yellow"))
        return None
    
    with open(file_path, 'r') as f:
        return json.load(f)

def plot_calibration_results(calibration_data):
    """Crea grafici visuali dei risultati calibrazione"""
    
    # Setup figure
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Confidence Calibration Results', fontsize=16, fontweight='bold')
    
    # Extract data
    metadata = calibration_data['metadata']
    xgb_cal = calibration_data['xgb_calibration']
    rl_cal = calibration_data['rl_calibration']
    
    # 1. XGBoost Calibration Chart
    ax1 = axes[0, 0]
    raw_ranges = [f"{int(r['raw_range'][0]*100)}-{int(r['raw_range'][1]*100)}%" for r in xgb_cal]
    calibrated_values = [r['calibrated_value'] * 100 for r in xgb_cal]
    raw_midpoints = [(r['raw_range'][0] + r['raw_range'][1]) / 2 * 100 for r in xgb_cal]
    
    x = np.arange(len(raw_ranges))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, raw_midpoints, width, label='Raw Confidence', color='lightblue', alpha=0.7)
    bars2 = ax1.bar(x + width/2, calibrated_values, width, label='Calibrated (Real Win Rate)', color='orange', alpha=0.7)
    
    ax1.set_ylabel('Confidence / Win Rate (%)', fontweight='bold')
    ax1.set_title('XGBoost Confidence Calibration', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(raw_ranges, rotation=45, ha='right')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50% baseline')
    
    # Add value labels
    for bar in bars2:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    
    # 2. Sample Distribution
    ax2 = axes[0, 1]
    samples = [r['samples'] for r in xgb_cal]
    wins = [r['wins'] for r in xgb_cal]
    losses = [r['losses'] for r in xgb_cal]
    
    ax2.bar(x, wins, width, label='Wins', color='green', alpha=0.7)
    ax2.bar(x, losses, width, bottom=wins, label='Losses', color='red', alpha=0.7)
    
    ax2.set_ylabel('Number of Trades', fontweight='bold')
    ax2.set_title('Trade Distribution by Confidence Range', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(raw_ranges, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Add total labels
    for i, (w, l) in enumerate(zip(wins, losses)):
        total = w + l
        ax2.text(i, total + 2, f'{total}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # 3. RL Calibration Chart
    ax3 = axes[1, 0]
    rl_raw_ranges = [f"{int(r['raw_range'][0]*100)}-{int(r['raw_range'][1]*100)}%" for r in rl_cal]
    rl_calibrated_values = [r['calibrated_value'] * 100 for r in rl_cal]
    rl_raw_midpoints = [(r['raw_range'][0] + r['raw_range'][1]) / 2 * 100 for r in rl_cal]
    
    x_rl = np.arange(len(rl_raw_ranges))
    
    bars3 = ax3.bar(x_rl - width/2, rl_raw_midpoints, width, label='Raw Confidence', color='lightblue', alpha=0.7)
    bars4 = ax3.bar(x_rl + width/2, rl_calibrated_values, width, label='Calibrated (Real Win Rate)', color='purple', alpha=0.7)
    
    ax3.set_ylabel('Confidence / Win Rate (%)', fontweight='bold')
    ax3.set_title('RL Agent Confidence Calibration', fontweight='bold')
    ax3.set_xticks(x_rl)
    ax3.set_xticklabels(rl_raw_ranges, rotation=45, ha='right')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.axhline(y=50, color='red', linestyle='--', alpha=0.5)
    
    # Add value labels
    for bar in bars4:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
    
    # 4. Summary Statistics
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    total_trades = metadata['total_trades']
    period = metadata['backtest_period']
    
    summary_text = f"""
📊 CALIBRATION SUMMARY
{'='*40}

Total Trades Analyzed: {total_trades}
Backtest Period: {period}

Stop Loss: {metadata.get('stop_loss', 'N/A')}
Trailing Trigger: {metadata.get('trailing_trigger', 'N/A')}
Trailing Distance: {metadata.get('trailing_distance', 'N/A')}

🎯 XGBoost Ranges: {len(xgb_cal)}
🤖 RL Ranges: {len(rl_cal)}

KEY INSIGHT:
The calibrated values show the REAL
win rate based on historical backtest.

Example:
• Model says 95% confidence
• Calibrated to 73% actual win rate
• Meaning: ~3 out of 10 will lose

This prevents overconfidence and
improves risk management!
"""
    
    ax4.text(0.1, 0.95, summary_text, transform=ax4.transAxes,
            fontsize=11, verticalalignment='top',
            fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    
    # Save figure
    output_file = 'visualizations/calibration_results.png'
    Path('visualizations').mkdir(exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(colored(f"\n✅ Visualization saved: {output_file}", "green"))
    
    plt.show()

def print_summary_table(calibration_data):
    """Stampa tabella riassuntiva testuale"""
    print(colored("\n" + "="*80, "cyan"))
    print(colored("📊 XGBoost CALIBRATION TABLE", "cyan", attrs=['bold']))
    print(colored("="*80, "cyan"))
    
    print(f"{'Range':<15} {'Raw Mid':<12} {'Calibrated':<15} {'Samples':<10} {'Win Rate':<12}")
    print("-" * 80)
    
    for r in calibration_data['xgb_calibration']:
        range_str = f"{int(r['raw_range'][0]*100)}-{int(r['raw_range'][1]*100)}%"
        raw_mid = (r['raw_range'][0] + r['raw_range'][1]) / 2 * 100
        calibrated = r['calibrated_value'] * 100
        samples = r['samples']
        wins = r['wins']
        losses = r['losses']
        win_rate = (wins / samples * 100) if samples > 0 else 0
        
        print(f"{range_str:<15} {raw_mid:>6.1f}%     {calibrated:>6.1f}%        {samples:<10} {win_rate:>5.1f}%  ({wins}W/{losses}L)")
    
    print(colored("\n" + "="*80, "cyan"))
    print(colored("🤖 RL CALIBRATION TABLE", "cyan", attrs=['bold']))
    print(colored("="*80, "cyan"))
    
    print(f"{'Range':<15} {'Raw Mid':<12} {'Calibrated':<15} {'Samples':<10} {'Win Rate':<12}")
    print("-" * 80)
    
    for r in calibration_data['rl_calibration']:
        range_str = f"{int(r['raw_range'][0]*100)}-{int(r['raw_range'][1]*100)}%"
        raw_mid = (r['raw_range'][0] + r['raw_range'][1]) / 2 * 100
        calibrated = r['calibrated_value'] * 100
        samples = r['samples']
        wins = r['wins']
        losses = r['losses']
        win_rate = (wins / samples * 100) if samples > 0 else 0
        
        print(f"{range_str:<15} {raw_mid:>6.1f}%     {calibrated:>6.1f}%        {samples:<10} {win_rate:>5.1f}%  ({wins}W/{losses}L)")
    
    print(colored("\n" + "="*80, "cyan"))

def main():
    """Main entry point"""
    print(colored("\n🎨 CALIBRATION RESULTS VISUALIZER", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    # Load data
    calibration_data = load_calibration_data()
    
    if not calibration_data:
        return
    
    # Print summary
    print_summary_table(calibration_data)
    
    # Create plots
    print(colored("\n📊 Creating visualizations...", "yellow"))
    plot_calibration_results(calibration_data)
    
    print(colored("\n✅ Done! Check visualizations/calibration_results.png", "green"))

if __name__ == "__main__":
    main()
