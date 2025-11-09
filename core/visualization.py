"""
Visualization Module for Trading Bot

FEATURES:
- Training metrics visualization (confusion matrix, feature importance, etc.)
- Performance plots and statistics
- Automatic saving of charts as images
"""

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Set matplotlib backend for headless operation
import matplotlib
matplotlib.use('Agg')

class TradingVisualizer:
    """
    Visualization system for trading bot training analysis
    """
    
    def __init__(self):
        self.output_dir = "visualizations"
        self._ensure_output_dir()
        
        # Set style
        plt.style.use('dark_background')
        sns.set_palette("husl")
        
        logging.info("📊 Trading Visualizer initialized")
    
    def _ensure_output_dir(self):
        """Create output directory for visualizations"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(f"{self.output_dir}/training", exist_ok=True)
    
    def plot_training_metrics(self, 
                            y_true: np.ndarray, 
                            y_pred: np.ndarray, 
                            y_prob: np.ndarray,
                            feature_importance: np.ndarray,
                            feature_names: List[str],
                            timeframe: str,
                            metrics: Dict) -> str:
        """
        Create comprehensive training visualization
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_prob: Prediction probabilities
            feature_importance: Feature importance scores
            feature_names: List of feature names
            timeframe: Trading timeframe
            metrics: Training metrics dictionary
            
        Returns:
            str: Path to saved image
        """
        try:
            fig, axes = plt.subplots(2, 3, figsize=(20, 12))
            fig.suptitle(f'XGBoost Training Results - {timeframe}', fontsize=16, color='white')
            
            # 1. Confusion Matrix
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(y_true, y_pred)
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                       xticklabels=['SELL', 'BUY', 'NEUTRAL'],
                       yticklabels=['SELL', 'BUY', 'NEUTRAL'],
                       ax=axes[0,0])
            axes[0,0].set_title('Confusion Matrix', color='white')
            axes[0,0].set_xlabel('Predicted', color='white')
            axes[0,0].set_ylabel('Actual', color='white')
            
            # 2. Class Distribution
            unique, counts = np.unique(y_true, return_counts=True)
            class_names = ['SELL', 'BUY', 'NEUTRAL']
            colors = ['#ff4444', '#44ff44', '#4444ff']
            bars = axes[0,1].bar([class_names[i] for i in unique], counts, color=colors)
            axes[0,1].set_title('Class Distribution', color='white')
            axes[0,1].set_ylabel('Count', color='white')
            
            # Add count labels on bars
            for bar, count in zip(bars, counts):
                axes[0,1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                              str(count), ha='center', va='bottom', color='white')
            
            # 3. Feature Importance (Top 15)
            if len(feature_importance) > 0 and len(feature_names) > 0:
                top_n = min(15, len(feature_importance))
                top_idx = np.argsort(feature_importance)[-top_n:]
                top_features = [feature_names[i] if i < len(feature_names) else f'Feature_{i}' 
                              for i in top_idx]
                top_importance = feature_importance[top_idx]
                
                y_pos = np.arange(len(top_features))
                axes[0,2].barh(y_pos, top_importance, color='skyblue')
                axes[0,2].set_yticks(y_pos)
                axes[0,2].set_yticklabels(top_features, fontsize=8, color='white')
                axes[0,2].set_title('Top Feature Importance', color='white')
                axes[0,2].set_xlabel('Importance', color='white')
            
            # 4. Prediction Probabilities Distribution
            if y_prob is not None and len(y_prob.shape) > 1:
                for class_idx in range(y_prob.shape[1]):
                    class_probs = y_prob[:, class_idx]
                    axes[1,0].hist(class_probs, alpha=0.7, bins=30, 
                                  label=class_names[class_idx], color=colors[class_idx])
                axes[1,0].set_title('Prediction Confidence Distribution', color='white')
                axes[1,0].set_xlabel('Probability', color='white')
                axes[1,0].set_ylabel('Count', color='white')
                axes[1,0].legend()
            
            # 5. Performance Metrics
            metrics_text = []
            metrics_text.append(f"Accuracy: {metrics.get('val_accuracy', 0):.3f}")
            metrics_text.append(f"Precision: {metrics.get('val_precision', 0):.3f}")
            metrics_text.append(f"Recall: {metrics.get('val_recall', 0):.3f}")
            metrics_text.append(f"F1-Score: {metrics.get('val_f1', 0):.3f}")
            metrics_text.append(f"CV Mean: {metrics.get('cv_mean_accuracy', 0):.3f}")
            metrics_text.append(f"CV Std: {metrics.get('cv_std_accuracy', 0):.3f}")
            
            axes[1,1].text(0.1, 0.9, '\n'.join(metrics_text), 
                          transform=axes[1,1].transAxes, fontsize=12,
                          verticalalignment='top', color='white',
                          bbox=dict(boxstyle='round', facecolor='navy', alpha=0.8))
            axes[1,1].set_title('Performance Metrics', color='white')
            axes[1,1].axis('off')
            
            # 6. Classification Report Heatmap
            from sklearn.metrics import classification_report
            report = classification_report(y_true, y_pred, 
                                         target_names=class_names,
                                         output_dict=True, zero_division=0)
            
            # Extract metrics for heatmap
            metrics_matrix = []
            metric_names = ['precision', 'recall', 'f1-score']
            for metric in metric_names:
                row = [report[class_name][metric] for class_name in class_names]
                metrics_matrix.append(row)
            
            sns.heatmap(metrics_matrix, annot=True, fmt='.3f', cmap='RdYlGn',
                       xticklabels=class_names, yticklabels=metric_names,
                       ax=axes[1,2], vmin=0, vmax=1)
            axes[1,2].set_title('Classification Report Heatmap', color='white')
            
            plt.tight_layout()
            
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_metrics_{timeframe}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, "training", filename)
            
            plt.savefig(filepath, dpi=300, bbox_inches='tight', 
                       facecolor='black', edgecolor='none')
            plt.close()
            
            logging.info(f"📊 Training metrics saved: {filepath}")
            return filepath
            
        except Exception as e:
            logging.error(f"Error creating training visualization: {e}")
            return None


# Global instance for easy access
visualizer = TradingVisualizer()

def save_training_metrics(y_true, y_pred, y_prob, feature_importance, feature_names, timeframe, metrics):
    """Convenient function to save training metrics"""
    return visualizer.plot_training_metrics(y_true, y_pred, y_prob, feature_importance, 
                                          feature_names, timeframe, metrics)
