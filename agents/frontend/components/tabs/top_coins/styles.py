"""
CSS styles for Top 100 Coins tab tables.

Provides consistent dark theme styling for:
- Crypto table (Top 100 list)
"""


def get_crypto_table_css() -> str:
    """Returns CSS for the crypto table with dark theme."""
    return """
    <style>
        .crypto-table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(13, 17, 23, 0.9);
            border-radius: 12px;
            overflow: hidden;
            font-family: 'Rajdhani', sans-serif;
        }
        .crypto-table th {
            background: linear-gradient(135deg, #161b26 0%, #1e2a38 100%);
            color: #00ffff !important;
            padding: 15px 20px;
            text-align: left;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 2px solid rgba(0, 255, 255, 0.3);
            font-size: 0.9rem;
        }
        .crypto-table td {
            color: #ffffff !important;
            padding: 12px 20px;
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
            font-size: 1rem;
        }
        .crypto-table tr:hover td {
            background: rgba(0, 255, 255, 0.1);
        }
        .crypto-table tr:nth-child(even) td {
            background: rgba(0, 0, 0, 0.2);
        }
        .rank-col {
            color: #00ffff !important;
            font-weight: 700;
            font-family: 'Orbitron', sans-serif;
        }
        .coin-col {
            color: #ffffff !important;
            font-weight: 600;
        }
        .vol-col {
            color: #00ff88 !important;
            font-weight: 600;
        }
        .pct-col {
            color: #fbbf24 !important;
        }
        .table-container {
            max-height: 500px;
            overflow-y: auto;
            border-radius: 12px;
            border: 1px solid rgba(0, 255, 255, 0.3);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.1);
        }
    </style>
    """


def render_crypto_table_html(df_display, total_vol: float) -> str:
    """
    Generate HTML table for Top 100 coins.
    
    Args:
        df_display: DataFrame with columns: rank, coin, volume_24h, Volume 24h, % of Total
        total_vol: Total volume for percentage calculation
        
    Returns:
        Complete HTML string for the table
    """
    table_html = get_crypto_table_css()
    
    table_html += """
    <div class="table-container">
    <table class="crypto-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Coin</th>
                <th>Volume 24h</th>
                <th>% of Total</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for _, row in df_display.iterrows():
        table_html += f"""
            <tr>
                <td class="rank-col">{row['rank']}</td>
                <td class="coin-col">{row['coin']}</td>
                <td class="vol-col">{row['Volume 24h']}</td>
                <td class="pct-col">{row['% of Total']}</td>
            </tr>
        """
    
    table_html += """
        </tbody>
    </table>
    </div>
    """
    
    return table_html


__all__ = ['get_crypto_table_css', 'render_crypto_table_html']
