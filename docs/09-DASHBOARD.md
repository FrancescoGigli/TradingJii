# 📖 09 - Dashboard PyQt6

> **GUI Real-time con 4 tabs**

---

## 🖥️ Overview Dashboard

Il sistema include una **dashboard PyQt6** real-time che mostra posizioni attive, trade chiusi, statistiche e memoria adaptive.

```
DASHBOARD STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────┐
│  TRADING DASHBOARD - Real-time Monitor         │
├─────────────────────────────────────────────────┤
│  [Active] [Closed] [Statistics] [Adaptive]     │ ← Tabs
├─────────────────────────────────────────────────┤
│                                                 │
│  TAB CONTENT (auto-refresh ogni 30s)           │
│                                                 │
│  • Color-coded rows (verde/rosso/giallo)       │
│  • Sortable columns                            │
│  • Real-time P&L updates                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 🎨 Tab 1: Active Positions

### **Columns**

```
┌─────────┬──────┬────────┬────────┬─────────┬─────────┬──────────┬──────────┐
│ Symbol  │ Side │ Entry  │Current │   P&L   │   ROE   │ Duration │ Conf %   │
├─────────┼──────┼────────┼────────┼─────────┼─────────┼──────────┼──────────┤
│ SOL     │ BUY  │ 100.50 │ 105.20 │ +$23.50 │ +23.5%  │   45min  │   77%    │
│ AVAX    │ BUY  │  40.00 │  41.20 │ +$15.00 │ +15.0%  │   30min  │   72%    │
│ MATIC   │ BUY  │   1.00 │   0.98 │  -$5.00 │  -5.0%  │   15min  │   68%    │
└─────────┴──────┴────────┴────────┴─────────┴─────────┴──────────┴──────────┘
```

### **Color Coding**

- 🟢 **Verde**: ROE > +5%
- 🔴 **Rosso**: ROE < -2%
- 🟡 **Giallo**: -2% ≤ ROE ≤ +5%

### **Update Frequency**

```python
# Background task
async def dashboard_update_task():
    while True:
        # Fetch latest positions
        positions = position_manager.get_active_positions()
        
        # Update table
        dashboard.update_active_tab(positions)
        
        # Wait 30s
        await asyncio.sleep(30)
```

### **Implementation**

```python
class ActivePositionsTab(QWidget):
    def __init__(self):
        super().__init__()
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            'Symbol', 'Side', 'Entry', 'Current', 
            'P&L', 'ROE%', 'Duration', 'Conf%'
        ])
        
        # Enable sorting
        self.table.setSortingEnabled(True)
        
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def update_data(self, positions):
        """Update table con nuovi dati"""
        self.table.setRowCount(len(positions))
        
        for row, pos in enumerate(positions):
            # Set cell values
            self.table.setItem(row, 0, QTableWidgetItem(pos.symbol.split('/')[0]))
            self.table.setItem(row, 1, QTableWidgetItem(pos.side.upper()))
            self.table.setItem(row, 2, QTableWidgetItem(f"${pos.entry_price:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"${pos.current_price:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"${pos.unrealized_pnl:+.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{pos.roe_percentage:+.1f}%"))
            
            # Duration
            duration = self._calculate_duration(pos.open_time)
            self.table.setItem(row, 6, QTableWidgetItem(duration))
            
            # Confidence
            self.table.setItem(row, 7, QTableWidgetItem(f"{pos.confidence*100:.0f}%"))
            
            # Apply color coding
            self._apply_row_color(row, pos.roe_percentage)
    
    def _apply_row_color(self, row, roe):
        """Applica colore a riga basato su ROE"""
        if roe > 5:
            color = QColor(200, 255, 200)  # Light green
        elif roe < -2:
            color = QColor(255, 200, 200)  # Light red
        else:
            color = QColor(255, 255, 200)  # Light yellow
        
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(color)
```

---

## 📊 Tab 2: Closed Trades

### **Columns**

```
┌─────────┬──────┬────────┬──────┬─────────┬─────────┬──────────┬──────────────┐
│ Symbol  │ Side │ Entry  │ Exit │   P&L   │   ROE   │ Duration │ Close Reason │
├─────────┼──────┼────────┼──────┼─────────┼─────────┼──────────┼──────────────┤
│ SOL     │ BUY  │ 100.50 │110.0 │ +$47.50 │ +47.5%  │   2h15m  │ partial_exit │
│ AVAX    │ BUY  │  40.00 │ 38.0 │ -$12.50 │ -25.0%  │   45min  │ stop_loss    │
│ ETH     │ BUY  │3200.00 │3280  │ +$20.00 │ +20.0%  │   1h30m  │ early_exit   │
└─────────┴──────┴────────┴──────┴─────────┴─────────┴──────────┴──────────────┘
```

### **Filters**

- **All Trades**
- **Wins Only** (ROE > 0)
- **Losses Only** (ROE ≤ 0)
- **Last 24h**
- **Last 7 days**

### **Stats Summary**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SESSION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Trades:     45
Win Rate:         60.0% (27W / 18L)
Total P&L:        +$385.50
Avg Win:          +$28.50 (+48.2% ROE)
Avg Loss:         -$13.80 (-18.5% ROE)
Largest Win:      +$95.00 (+125% ROE)
Largest Loss:     -$25.00 (-25% ROE SL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📈 Tab 3: Statistics

### **Performance Metrics**

```python
class StatisticsTab(QWidget):
    def __init__(self):
        super().__init__()
        
        # Create sections
        self.session_group = self._create_session_section()
        self.trading_group = self._create_trading_section()
        self.risk_group = self._create_risk_section()
        
        layout = QVBoxLayout()
        layout.addWidget(self.session_group)
        layout.addWidget(self.trading_group)
        layout.addWidget(self.risk_group)
        self.setLayout(layout)
```

### **Section 1: Session Overview**

```
┌─────────────────────────────────────────┐
│  SESSION OVERVIEW                       │
├─────────────────────────────────────────┤
│  Start Time:     2025-01-07 09:00:00   │
│  Duration:       8h 15m                 │
│  Initial Balance: $500.00               │
│  Current Balance: $885.50               │
│  Total P&L:      +$385.50 (+77.1%)     │
│  Peak Balance:   $920.00                │
│  Max Drawdown:   -$45.00 (-8.2%)       │
└─────────────────────────────────────────┘
```

### **Section 2: Trading Stats**

```
┌─────────────────────────────────────────┐
│  TRADING PERFORMANCE                    │
├─────────────────────────────────────────┤
│  Total Trades:    45                    │
│  Wins:            27 (60.0%)            │
│  Losses:          18 (40.0%)            │
│  Avg Win:         +48.2% ROE            │
│  Avg Loss:        -18.5% ROE            │
│  Win/Loss Ratio:  2.6:1                 │
│  Profit Factor:   2.8                   │
│  Sharpe Ratio:    1.95                  │
└─────────────────────────────────────────┘
```

### **Section 3: Risk Metrics**

```
┌─────────────────────────────────────────┐
│  RISK MANAGEMENT                        │
├─────────────────────────────────────────┤
│  Active Positions:  3 / 5 max          │
│  Used Margin:       $150.00 (30%)      │
│  Available Margin:  $350.00 (70%)      │
│  Max Risk (SL):     $45.00 (9%)        │
│  Actual Max Loss:   -$25.00 (5%)       │
│  SL Triggers:       5 (11.1%)          │
│  Early Exits:       8 (17.8%)          │
│  Partial Exits:     12 (44.4% of wins) │
└─────────────────────────────────────────┘
```

---

## 🎯 Tab 4: Adaptive Memory

### **Symbol Performance Table**

```
┌─────────┬─────────┬─────────┬────────┬──────────┬─────────┐
│ Symbol  │  Size   │ Status  │ Trades │  W - L   │ Last P&L│
├─────────┼─────────┼─────────┼────────┼──────────┼─────────┤
│ SOL     │ $63.50  │ 📈 GROW │   15   │ 10W - 5L │  +8.5%  │
│ AVAX    │ $51.20  │ 📊 STAB │   10   │  6W - 4L │  +1.2%  │
│ MATIC   │ $58.30  │ 📈 GROW │   11   │  8W - 3L │  +5.8%  │
│ LINK    │ $47.50  │ 📉 SHRI │    9   │  4W - 5L │  -2.5%  │
│ DOGE    │  BLOCK  │ 🔒 BLK2 │    9   │  3W - 6L │  -5.8%  │
│ SHIB    │  BLOCK  │ 🔒 BLK1 │    7   │  2W - 5L │  -4.2%  │
└─────────┴─────────┴─────────┴────────┴──────────┴─────────┘

LEGEND:
  📈 GROWING:   Size aumentata (winners)
  📊 STABLE:    Size stabile
  📉 SHRINKING: Size ridotta (recent losses)
  🔒 BLK#:      Blocked per # cicli
```

### **Overall Stats**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADAPTIVE SIZING STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Current Cycle:     #45
Total Symbols:     12
Active:            10
Blocked:           2
Overall Win Rate:  60.0% (27W / 18L)
Kelly Active:      5 symbols (10+ trades each)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🔄 Auto-Update Mechanism

### **QTimer Integration**

```python
class TradingDashboard(QMainWindow):
    def __init__(self, position_manager):
        super().__init__()
        self.position_manager = position_manager
        
        # Setup tabs
        self.tabs = QTabWidget()
        self.active_tab = ActivePositionsTab()
        self.closed_tab = ClosedTradesTab()
        self.stats_tab = StatisticsTab()
        self.adaptive_tab = AdaptiveMemoryTab()
        
        self.tabs.addTab(self.active_tab, "Active Positions")
        self.tabs.addTab(self.closed_tab, "Closed Trades")
        self.tabs.addTab(self.stats_tab, "Statistics")
        self.tabs.addTab(self.adaptive_tab, "Adaptive Memory")
        
        self.setCentralWidget(self.tabs)
        
        # Setup auto-update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_data)
        self.update_timer.start(30000)  # 30 seconds
        
        # Initial update
        self.refresh_data()
    
    def refresh_data(self):
        """Refresh all tabs con dati aggiornati"""
        try:
            # Get latest data
            active_pos = self.position_manager.get_active_positions()
            closed_pos = self.position_manager.get_closed_positions()
            session_stats = self.position_manager.get_session_summary()
            
            # Update each tab
            self.active_tab.update_data(active_pos)
            self.closed_tab.update_data(closed_pos)
            self.stats_tab.update_data(session_stats)
            
            # Adaptive memory (if enabled)
            if hasattr(self, 'adaptive_sizing'):
                adaptive_stats = self.adaptive_sizing.get_memory_stats()
                self.adaptive_tab.update_data(adaptive_stats)
            
        except Exception as e:
            logging.error(f"Dashboard refresh error: {e}")
```

---

## 🎨 Styling

### **Dark Theme**

```python
def apply_dark_theme(app):
    """Apply dark theme to dashboard"""
    
    stylesheet = """
    QMainWindow {
        background-color: #2b2b2b;
        color: #ffffff;
    }
    
    QTableWidget {
        background-color: #3c3c3c;
        color: #ffffff;
        gridline-color: #555555;
    }
    
    QHeaderView::section {
        background-color: #4a4a4a;
        color: #ffffff;
        font-weight: bold;
        padding: 5px;
        border: 1px solid #555555;
    }
    
    QTabWidget::pane {
        border: 1px solid #555555;
        background-color: #2b2b2b;
    }
    
    QTabBar::tab {
        background-color: #3c3c3c;
        color: #ffffff;
        padding: 10px;
        border: 1px solid #555555;
    }
    
    QTabBar::tab:selected {
        background-color: #4a4a4a;
    }
    """
    
    app.setStyleSheet(stylesheet)
```

---

## 🚀 Launch Integration

### **Integration con Asyncio (qasync)**

```python
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

# Create QApplication
app = QApplication(sys.argv)

# Create qasync event loop
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

# Create dashboard
dashboard = TradingDashboard(position_manager)
dashboard.show()

# Run main trading loop with GUI
try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    logging.info("Interrupted by user")
finally:
    loop.close()
```

---

## ⚙️ Configuration

```python
# Update frequency
DASHBOARD_UPDATE_INTERVAL = 30  # seconds

# Window settings
DASHBOARD_WIDTH = 1200
DASHBOARD_HEIGHT = 800
DASHBOARD_TITLE = "Trading Bot Dashboard"

# Table settings
TABLE_FONT_SIZE = 10
TABLE_ROW_HEIGHT = 30

# Colors
COLOR_WIN = QColor(200, 255, 200)    # Light green
COLOR_LOSS = QColor(255, 200, 200)   # Light red
COLOR_NEUTRAL = QColor(255, 255, 200) # Light yellow
```

---

## 🎯 Key Features

### **1. Real-time Updates**
- Auto-refresh ogni 30s
- Live P&L tracking
- Color-coded visual feedback

### **2. Multiple Views**
- Active positions monitoring
- Historical trades review
- Performance statistics
- Adaptive memory visualization

### **3. User-Friendly**
- Sortable columns
- Filterable data
- Clear color coding
- Responsive layout

### **4. Thread-Safe**
- Safe concurrent access
- No race conditions
- Smooth updates

---

## 📚 Final Note

**10-CONFIGURAZIONE.md** - Prossimo e ultimo documento: guida completa a tutti i parametri di config.py

---

**🎯 KEY TAKEAWAY**: La dashboard PyQt6 fornisce monitoring real-time user-friendly con 4 tabs specializzate, auto-update ogni 30s, e integrazione perfetta con qasync per operazioni async.
