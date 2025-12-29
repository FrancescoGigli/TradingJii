@echo off
setlocal enabledelayedexpansion

:: ================================================================
:: 🚀 TRAE CONTAINER MANAGER
:: ================================================================
:: Script di gestione per il sistema crypto trading multi-agente
:: Gestisce rebuild, log e controllo container
:: ================================================================

title 🚀 Trae Container Manager

:menu
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                  🚀 TRAE CONTAINER MANAGER                         ║
echo ║            Sistema Crypto Trading Multi-Agente                     ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 📊 SISTEMA STATUS:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr "crypto" >nul
if errorlevel 1 (
    echo    🔴 Nessun container attivo
) else (
    echo    🟢 Container attivi trovati
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr "crypto"
)
echo.
echo ┌─────────────────────────────────────────────────────────────────┐
echo │                         📋 OPZIONI DISPONIBILI                    │
echo ├─────────────────────────────────────────────────────────────────┤
echo │                                                                 │
echo │  🔨 1. REBUILD COMPLETO DA ZERO                                  │
echo │     • Stoppa tutti i container                                   │
echo │     • Rimuove immagini e volumi                                  │
echo │     • Ricostruisce tutto da capo                                 │
echo │                                                                 │
echo │  ⚡ 2. QUICK START (Avvio Rapido)                               │
echo │     • Avvia solo i container essenziali                          │
echo │     • Rebuild automatico se necessario                           │
echo │                                                                 │
echo │  📊 3. STATUS DETTAGLIATO                                        │
echo │     • Stato completo di tutti i componenti                       │
echo │     • Informazioni sui volumi e network                          │
echo │                                                                 │
echo │  📋 4. LOG DATA FETCHER                                          │
echo │     • Log in tempo reale dell'agente dati                        │
echo │     • Scroll automatico attivo                                   │
echo │                                                                 │
echo │  📈 5. LOG FRONTEND                                              │
echo │     • Log del dashboard Streamlit                                │
echo │     • Scroll automatico attivo                                   │
echo │                                                                 │
echo │  🔍 6. LOG TUTTI GLI AGENTI                                     │
echo │     • Log combinati di tutti i container                         │
echo │     • Visualizzazione unificata                                  │
echo │                                                                 │
echo │  🛑 7. STOP TUTTO                                                │
echo │     • Ferma tutti i container in sicurezza                       │
echo │                                                                 │
echo │  🧹 8. CLEAN SYSTEM                                              │
echo │     • Rimuove TUTTO: container, immagini, volumi                 │
echo │     • ATTENZIONE: Cancella tutti i dati!                         │
echo │                                                                 │
echo │  🔧 9. DIAGNOSTICHE                                              │
echo │     • Comandi di troubleshooting                                 │
echo │     • Verifica configurazione                                    │
echo │                                                                 │
echo │  🚪 0. ESCI                                                      │
echo │     • Esci dal manager                                           │
echo │                                                                 │
echo └─────────────────────────────────────────────────────────────────┘
echo.
set /p choice="👉 Seleziona un'opzione (0-9): "

if "%choice%"=="1" goto rebuild
if "%choice%"=="2" goto quickstart
if "%choice%"=="3" goto status
if "%choice%"=="4" goto log_fetcher
if "%choice%"=="5" goto log_frontend
if "%choice%"=="6" goto log_all
if "%choice%"=="7" goto stop_all
if "%choice%"=="8" goto clean_system
if "%choice%"=="9" goto diagnostics
if "%choice%"=="0" goto exit

echo.
echo ❌ Opzione non valida! Riprova...
pause
goto menu

:rebuild
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                    🔨 REBUILD COMPLETO DA ZERO                     ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo ⚠️  ATTENZIONE: Questa operazione:
echo    • Fermerà tutti i container
echo    • Rimuoverà le immagini Docker
echo    • Eliminerà i volumi (PERDERAI TUTTI I DATI!)
echo    • Ricostruirà tutto da capo
echo.
set /p confirm="🚀 Sei sicuro di voler procedere? (S/N): "
if /i not "%confirm%"=="S" goto menu

echo.
echo 🔄 Step 1/5: Fermando tutti i container...
docker-compose down
echo ✅ Container fermati

echo.
echo 🗑️  Step 2/5: Rimuovendo immagini...
docker-compose down --rmi all --volumes --remove-orphans
echo ✅ Immagini rimosse

echo.
echo 🧹 Step 3/5: Pulizia aggiuntiva...
docker system prune -f
echo ✅ Sistema pulito

echo.
echo 🔨 Step 4/5: Ricostruendo le immagini...
docker-compose build --no-cache
echo ✅ Immagini ricostruite

echo.
echo 🚀 Step 5/5: Avviando il sistema...
docker-compose up -d

echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                      ✅ REBUILD COMPLETATO!                        ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 📊 Container avviati:
docker-compose ps
echo.
echo 📈 Accesso al dashboard: http://localhost:8501
echo ⏰ Attendi 2-3 minuti per il primo caricamento dati
echo.
pause
goto menu

:quickstart
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                      ⚡ QUICK START                                ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

:: Verifica se esiste già il file .env
if not exist ".env" (
    echo ⚠️  File .env non trovato!
    echo.
    echo 📝 Creazione automatica del file .env...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo ✅ File .env creato da .env.example
        echo.
        echo 🔧 MODIFICA IL FILE .env CON LE TUE API KEYS:
        echo    • Apri il file .env
        echo    • Inserisci la tua BYBIT_API_KEY
        echo    • Inserisci la tua BYBIT_API_SECRET
        echo.
        notepad .env
        echo.
        set /p ready="✅ Hai configurato il file .env? (S/N): "
        if /i not "!ready!"=="S" goto menu
    ) else (
        echo ❌ File .env.example non trovato!
        pause
        goto menu
    )
)

echo.
echo 🔍 Verifica configurazione...
docker-compose config >nul 2>&1
if errorlevel 1 (
    echo ❌ Errore nella configurazione docker-compose!
    echo 🔧 Verifica il file .env e docker-compose.yml
    pause
    goto menu
)

echo ✅ Configurazione valida

echo.
echo 🚀 Avvio sistema...
docker-compose up -d --build

echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                       ✅ SISTEMA AVVIATO!                          ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 📊 Container status:
docker-compose ps
echo.
echo 🌐 Dashboard disponibile su: http://localhost:8501
echo ⏳ Data Fetcher sta scaricando i primi dati...
echo 📈 Attendi 2-3 minuti per il caricamento completo
echo.
pause
goto menu

:status
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                     📊 STATUS DETTAGLIATO                          ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

echo 🔍 CONTAINER STATUS:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker-compose ps
echo.

echo 🌐 NETWORK STATUS:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker network ls | findstr "trading"
echo.

echo 💾 VOLUMES STATUS:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker volume ls | findstr "crypto"
echo.

echo 📈 IMAGES STATUS:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker images | findstr "trae"
echo.

echo 💻 SYSTEM RESOURCES:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
echo.

echo 📊 DISK USAGE (Volumes):
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
for /f "tokens=*" %%i in ('docker volume inspect crypto-shared-data --format "{{.Mountpoint}}" 2^>nul') do (
    if exist "%%i" (
        echo Volume Path: %%i
        dir "%%i" 2>nul | findstr "trading_data.db"
    )
)
echo.

echo 🔧 DOCKER INFO:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker version --format "Client: {{.Client.Version}} | Server: {{.Server.Version}}"
echo.

pause
goto menu

:log_fetcher
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                    📋 LOG DATA FETCHER                             ║
echo ║                     (Press Ctrl+C to exit)                         ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

docker-compose logs -f data-fetcher
if errorlevel 1 (
    echo.
    echo ❌ Data Fetcher non trovato o non attivo
    echo 🔧 Prova prima: Quick Start o Rebuild
)
pause
goto menu

:log_frontend
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                     📈 LOG FRONTEND                                ║
echo ║                     (Press Ctrl+C to exit)                         ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

docker-compose logs -f frontend
if errorlevel 1 (
    echo.
    echo ❌ Frontend non trovato o non attivo
    echo 🔧 Prova prima: Quick Start o Rebuild
)
pause
goto menu

:log_all
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                   🔍 LOG TUTTI GLI AGENTI                          ║
echo ║                     (Press Ctrl+C to exit)                         ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

docker-compose logs -f
if errorlevel 1 (
    echo.
    echo ❌ Nessun container attivo trovato
    echo 🔧 Prova prima: Quick Start o Rebuild
)
pause
goto menu

:stop_all
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                       🛑 STOP TUTTO                                ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

docker-compose down
echo.
echo ✅ Tutti i container sono stati fermati
echo.
pause
goto menu

:clean_system
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                    🧹 CLEAN SYSTEM                                 ║
echo ║                  ⚠️  ATTENZIONE MASSIMA! ⚠️                         ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 🚨 Questa operazione ELIMINERÀ DEFINITIVAMENTE:
echo    ❌ Tutti i container
echo    ❌ Tutte le immagini Docker
echo    ❌ Tutti i volumi (DATABASE INCLUSO!)
echo    ❌ Tutti i dati del sistema
echo.
echo 💀 TUTTI I TUOI DATI CRYPTO VERRANNO PERDUTI!
echo.
set /p confirm="🚨 Digita 'DELETE EVERYTHING' per confermare: "
if not "%confirm%"=="DELETE EVERYTHING" (
    echo.
    echo ✅ Operazione annullata per sicurezza
    pause
    goto menu
)

echo.
echo 💀 ELIMINAZIONE IN CORSO...
echo.

echo 🛑 Stopping containers...
docker-compose down

echo 🗑️  Removing images...
docker-compose down --rmi all --volumes --remove-orphans

echo 🧹 Cleaning system...
docker system prune -af --volumes

echo 💥 Force cleaning...
docker rmi -f $(docker images -q) 2>nul
docker volume prune -f

echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                 💀 SISTEMA COMPLETAMENTE PULITO!                   ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 🆕 Per ricominciare, esegui: Quick Start
echo.
pause
goto menu

:diagnostics
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                      🔧 DIAGNOSTICHE                               ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.

echo 🔍 VERIFICA DOCKER:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker --version
docker-compose --version
echo.

echo 🔍 VERIFICA CONFIGURAZIONE:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if exist ".env" (
    echo ✅ File .env presente
    echo 📝 Prime 3 righe del .env:
    powershell "Get-Content .env | Select-Object -First 3"
) else (
    echo ❌ File .env mancante!
)

if exist "docker-compose.yml" (
    echo ✅ docker-compose.yml presente
) else (
    echo ❌ docker-compose.yml mancante!
)
echo.

echo 🔍 VERIFICA PORTI:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
netstat -an | findstr ":8501"
echo.

echo 🔍 TEST CONNESSIONE BYBIT:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
curl -s --connect-timeout 10 "https://api.bybit.com/v5/market/tickers?category=spot" >nul
if errorlevel 1 (
    echo ❌ Connessione Bybit fallita (controlla internet)
) else (
    echo ✅ Connessione Bybit OK
)
echo.

echo 🔍 LOG ERRORI RECENTI:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
docker-compose logs --tail=10 data-fetcher | findstr -i error
docker-compose logs --tail=10 frontend | findstr -i error
echo.

echo 🔍 INFORMAZIONI SISTEMA:
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
systeminfo | findstr "Total Physical Memory"
wmic os get freephysicalmemory /value 2>nul | findstr "FreePhysicalMemory"
echo.

pause
goto menu

:exit
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║                    👋 ARRIVEDERCI!                                 ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo 🚀 Trae Container Manager chiuso
echo 💡 Per riavviare: doppio click su manage_containers.bat
echo.
timeout /t 3 >nul
exit /b 0
