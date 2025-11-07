# 🤖 TRADE ANALYZER - Quick Reference

> **📚 Documentazione completa:** [docs/09-TRADE-ANALYZER.md](docs/09-TRADE-ANALYZER.md)

---

## 🎯 Cos'è?

Sistema AI-powered che analizza **predizione ML vs realtà** per ogni trade, usando ChatGPT per apprendimento continuo.

## ⚡ Quick Start

1. **Configurazione:**
   ```python
   # config.py (già configurato)
   LLM_ANALYSIS_ENABLED = True
   LLM_MODEL = 'gpt-4o-mini'
   ```

2. **API Key:**
   ```bash
   # .env file (già presente)
   OPENAI_API_KEY=sk-...
   ```

3. **Automatic:** Sistema già integrato, funziona automaticamente!

## 📊 Dove Vedere le Analisi

Ogni volta che un trade chiude, vedrai nel terminal:

```
═══════════════════════════════════════════════════════════════════
🤖 TRADE ANALYSIS: AVAX ❌
═══════════════════════════════════════════════════════════════════
📊 Outcome: LOSS | PnL: -12.5% ROE
🎯 Prediction: BUY @ 75% | Accuracy: overconfident
📊 Category: false_breakout

💡 Explanation: [Analisi dettagliata...]
✅ What Went Right: [...]
❌ What Went Wrong: [...]
🎯 Recommendations: [...]
🧠 ML Model Feedback: [...]
═══════════════════════════════════════════════════════════════════
```

## 💰 Costi

- ~$0.0006 per analisi
- 100 trade/mese = **$0.06/mese** (economicissimo!)

## 📚 Documentazione Completa

Per dettagli tecnici, workflow, esempi e configurazione avanzata:
👉 **[docs/09-TRADE-ANALYZER.md](docs/09-TRADE-ANALYZER.md)**

## 🔗 Guide Correlate

- [DOVE_VEDERE_ANALISI_CHATGPT.md](DOVE_VEDERE_ANALISI_CHATGPT.md) - Dove trovare le analisi
- [RIEPILOGO_SISTEMA_LLM_TRADE.md](RIEPILOGO_SISTEMA_LLM_TRADE.md) - Overview sistema LLM
- [FIX_TRADE_ANALYZER_ACTIVATION.md](FIX_TRADE_ANALYZER_ACTIVATION.md) - Troubleshooting
