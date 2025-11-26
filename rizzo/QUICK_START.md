# 🚀 Quick Start - Setup Rapido Trading Bot

## ✅ Hai già fatto:

1. ✅ Account Hyperliquid testnet creato
2. ✅ Database Supabase configurato
3. ✅ File `.env` creato

---

## 📋 Prossimi Step

### **1. Completa il File `.env`**

Apri il file `.env` e inserisci le tue chiavi:

```env
# HYPERLIQUID
PRIVATE_KEY=0xTUA_CHIAVE_QUI
WALLET_ADDRESS=0xTUO_INDIRIZZO_QUI

# OPENAI
OPENAI_API_KEY=sk-TUA_CHIAVE_OPENAI_QUI

# COINMARKETCAP
CMC_PRO_API_KEY=TUA_CHIAVE_CMC_QUI

# DATABASE - COPIA ESATTAMENTE QUESTO DA SUPABASE
DATABASE_URL=postgresql://postgres.xxx:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

⚠️ **IMPORTANTE**: 
- L'URL del database DEVE contenere **"pooler.supabase.com"**
- NON usare "db.xxx.supabase.co" (quello NON funziona!)

---

### **2. Ottieni Private Key da Hyperliquid**

Se hai creato account con email:

**Opzione A: Esporta da Hyperliquid**
- Vai su https://app.hyperliquid-testnet.xyz/
- Settings/Account → Export Private Key
- Copia

**Opzione B: Usa MetaMask** (CONSIGLIATO)
```
1. Installa MetaMask (browser extension)
2. Crea nuovo wallet
3. Salva seed phrase (importante!)
4. Export Private Key:
   - Menu (⋮) → Account details
   - Export Private Key
   - Copia
5. Richiedi fondi testnet:
   - Discord: https://discord.gg/hyperliquid
   - Canale: #testnet-faucet
   - Comando: /faucet <il_tuo_wallet_address>
```

---

### **3. Ottieni API Keys**

**OpenAI:**
```
1. Vai su https://platform.openai.com/api-keys
2. Create new key
3. Copia (sk-...)
```

**CoinMarketCap:**
```
1. Vai su https://coinmarketcap.com/api/
2. Sign up (gratis)
3. Piano "Basic" (10k calls/mese)
4. Copia API key
```

---

### **4. Installa Dipendenze**

```bash
pip install -r requirements.txt
```

---

### **5. Inizializza Database**

```bash
python -c "import db_utils; db_utils.init_db()"
```

Questo comando crea tutte le tabelle necessarie nel database.

---

### **6. Verifica Setup**

```bash
python setup_bot.py
```

Questo script controlla:
- ✅ File .env configurato
- ✅ Chiavi API presenti
- ✅ Dipendenze installate
- ✅ Database connesso
- ✅ Hyperliquid funzionante

---

### **7. Test**

```bash
python test_trading.py
```

---

### **8. Lancio! 🎉**

```bash
python main.py
```

---

## 🆘 Se Hai Problemi

**Database non si connette:**
```bash
# Verifica DATABASE_URL nel .env
# Deve contenere "pooler.supabase.com"
```

**Dipendenze mancanti:**
```bash
pip install -r requirements.txt
```

**Hyperliquid non funziona:**
```bash
# Verifica PRIVATE_KEY e WALLET_ADDRESS nel .env
```

---

## 📊 Dopo il Primo Lancio

Per vedere cosa ha fatto il bot:

**Controlla i log:**
```bash
# Il bot stampa le sue operazioni
```

**Query Database:**
```sql
-- Ultime operazioni
SELECT * FROM bot_operations ORDER BY created_at DESC LIMIT 5;

-- Stato account
SELECT * FROM account_snapshots ORDER BY created_at DESC LIMIT 1;
```

---

## ✅ Checklist Finale

Prima di lanciare `python main.py`:

- [ ] File `.env` completato con tutte le chiavi
- [ ] DATABASE_URL usa "pooler.supabase.com"
- [ ] Dipendenze installate (`pip install -r requirements.txt`)
- [ ] Database inizializzato (`db_utils.init_db()`)
- [ ] Test eseguito (`python test_trading.py`)
- [ ] `TESTNET = True` in main.py

---

## 🎯 Esempio .env Completo

```env
PRIVATE_KEY=0xabc123...
WALLET_ADDRESS=0x742d35Cc6634C0532925a3b844Bc9e...
OPENAI_API_KEY=sk-proj-abc123...
CMC_PRO_API_KEY=12345-abc-...
DATABASE_URL=postgresql://postgres.abc123:password@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

Tutto chiaro? 🚀
