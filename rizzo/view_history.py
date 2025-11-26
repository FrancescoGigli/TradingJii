import db_utils
import json

def view_last_decisions(limit=10):
    print(f"🔍 Recupero ultime {limit} operazioni dal Database...\n")
    
    # Recupera operazioni joinando con context per avere il prompt se necessario
    # Ma per ora usiamo la funzione basic e prendiamo il raw_payload
    
    ops = db_utils.get_recent_bot_operations(limit)
    
    if not ops:
        print("Nessuna operazione trovata nel DB.")
        return

    for op in ops:
        # op è un dict (raw_payload)
        # ma get_recent_bot_operations ritorna raw_payload che è il JSON salvato
        # che contiene "decisions": [...] se multiplo, o campi diretti se singolo.
        
        print("-" * 60)
        
        # Caso 1: Singola operazione (vecchio formato)
        if 'operation' in op:
            print(f"📅 Data: (Vedi DB timestamp)") 
            print(f"🪙 {op.get('symbol')} {op.get('operation').upper()}")
            print(f"📝 Reason: {op.get('reason')}")
            
        # Caso 2: Multiple decisions (nuovo formato)
        elif 'decisions' in op:
            print(f"📦 Batch di {len(op['decisions'])} decisioni:")
            for dec in op['decisions']:
                symbol = dec.get('symbol')
                categ = dec.get('operation')
                reason = dec.get('reason')
                if categ in ['open', 'close']: # Mostra solo azioni rilevanti o anche hold?
                    print(f"   👉 [{symbol}] {categ.upper()}")
                    print(f"      Motivo: {reason}")
                # else: print(f"   [{symbol}] HOLD")
        
    print("-" * 60)
    print("\n✅ Per vedere i dettagli completi (indicatori tecnici usati),")
    print("   devi consultare la tabella 'ai_contexts' nel database collegata tramite ID.")

if __name__ == "__main__":
    view_last_decisions()
