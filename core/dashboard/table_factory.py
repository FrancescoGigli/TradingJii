#!/usr/bin/env python3
"""
🏭 TABLE FACTORY

Factory per creare e configurare tabelle QTableWidget
con impostazioni standard per il dashboard.
"""

from PyQt6.QtWidgets import QTableWidget, QHeaderView
from PyQt6.QtCore import Qt


class TableFactory:
    """Factory per creare tabelle configurate"""
    
    @staticmethod
    def create_position_table() -> QTableWidget:
        """
        Crea una tabella per le posizioni attive
        
        Colonne: Symbol, Side, IM, Entry, Current, Stop Loss, Type, SL %, 
                 PnL %, PnL $, Liq. Price, Time, Status, Conf%, Weight, 
                 Adaptive Status, Open Reason
        """
        table = QTableWidget()
        table.setColumnCount(17)
        table.setHorizontalHeaderLabels([
            "Symbol", "Side", "IM", "Entry", "Current", "Stop Loss", "Type", 
            "SL %", "PnL %", "PnL $", "Liq. Price", "Time", "Status", 
            "Conf%", "Weight", "Adaptive Status", "Open Reason"
        ])
        
        TableFactory._apply_base_settings(table)
        TableFactory._set_position_column_widths(table)
        
        return table
    
    @staticmethod
    def create_closed_table() -> QTableWidget:
        """
        Crea una tabella per le posizioni chiuse
        
        Colonne: Symbol, ID, IM, Entry→Exit, PnL, Hold, 
                 Close Reason, Opened, Closed
        """
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "Symbol", "ID", "IM", "Entry→Exit", "PnL", "Hold", 
            "Close Reason", "Opened", "Closed"
        ])
        
        TableFactory._apply_base_settings(table)
        TableFactory._set_closed_column_widths(table)
        
        return table
    
    @staticmethod
    def _apply_base_settings(table: QTableWidget):
        """Applica impostazioni base comuni a tutte le tabelle"""
        # Visual settings
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Performance optimizations
        TableFactory.apply_performance_optimizations(table)
        
        # Sorting
        TableFactory.setup_sorting(table)
    
    @staticmethod
    def _set_position_column_widths(table: QTableWidget):
        """Imposta larghezze colonne per tabella posizioni"""
        header = table.horizontalHeader()
        
        # Fixed column widths for better performance
        widths = {
            0: 80,   # Symbol
            1: 110,  # Side
            2: 80,   # IM
            3: 90,   # Entry
            4: 90,   # Current
            5: 90,   # Stop Loss
            6: 80,   # Type
            7: 70,   # SL %
            8: 70,   # PnL %
            9: 90,   # PnL $
            10: 90,  # Liq. Price
            11: 70,  # Time
            12: 80,  # Status
            13: 60,  # Conf%
            14: 60,  # Weight
            15: 120, # Adaptive Status
        }
        
        for col, width in widths.items():
            table.setColumnWidth(col, width)
        
        # Last column (Open Reason) stretches
        header.setSectionResizeMode(16, QHeaderView.ResizeMode.Stretch)
    
    @staticmethod
    def _set_closed_column_widths(table: QTableWidget):
        """Imposta larghezze colonne per tabella chiuse"""
        header = table.horizontalHeader()
        
        # Auto-resize most columns to content
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # Close Reason column (index 6) stretches to fill remaining space
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
    
    @staticmethod
    def apply_performance_optimizations(table: QTableWidget):
        """
        Applica ottimizzazioni per performance
        - Scroll per pixel (più fluido)
        - Opaque paint event (più veloce)
        """
        table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    
    @staticmethod
    def setup_sorting(table: QTableWidget):
        """
        Abilita sorting interattivo sulle colonne
        - Click su header per ordinare
        - Indicator visibile
        """
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
    
    @staticmethod
    def disable_sorting_for_update(table: QTableWidget):
        """
        Disabilita sorting temporaneamente durante update
        CRITICO per performance - evita re-sorting ad ogni inserimento
        """
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
    
    @staticmethod
    def enable_sorting_after_update(table: QTableWidget):
        """
        Riabilita sorting e updates dopo popolamento tabella
        """
        table.setSortingEnabled(True)
        table.setUpdatesEnabled(True)
