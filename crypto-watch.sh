#!/bin/bash

# Crypto Market Monitor Script
# Fetches current prices and 24h changes for selected cryptocurrencies

# CoinGecko IDs for the requested coins
declare -A COINS
COINS["BTC"]="bitcoin"
COINS["ETH"]="ethereum"
COINS["SOL"]="solana"
COINS["TAO"]="bittensor"
COINS["TRX"]="tron"
COINS["BNB"]="binancecoin"
COINS["DOT"]="polkadot"
COINS["MON"]="monad"
COINS["ROBO"]="robonomics-network"
COINS["SKY"]="skale"
COINS["AAVE"]="aave"
COINS["ZEC"]="zcash"

# Build API request
IDS=""
for sym in "${!COINS[@]}"; do
  IDS+="${COINS[$sym]},"
done
IDS="${IDS%,}"

# Fetch from CoinGecko
DATA=$(curl -s "https://api.coingecko.com/api/v3/simple/price?ids=$IDS&vs_currencies=usd&include_24hr_change=true")

# Build message
RESULT="📊 *Crypto Watch — $(date '+%d/%m/%Y %H:%M')*"
RESULT+=$'\n\n'

# Format each coin
for sym in BTC ETH SOL TAO TRX BNB DOT MON ROBO SKY AAVE ZEC; do
  id="${COINS[$sym]}"
  price=$(echo "$DATA" | python3 -c "
import sys, json
data = json.load(sys.stdin)
d = data.get('$id', {})
p = d.get('usd', 0)
if p >= 1:
    print(f'\${p:,.2f}')
elif p >= 0.0001:
    print(f'\${p:.6f}')
else:
    print(f'\${p:.8f}')
")
  change=$(echo "$DATA" | python3 -c "
import sys, json
data = json.load(sys.stdin)
c = data.get('$id', {}).get('usd_24h_change', 0)
print(f'{c:+.2f}%')
")
  
  # Arrow
  if echo "$change" | grep -q "^+"; then
    arrow="🟢"
  elif echo "$change" | grep "0.00%"; then
    arrow="⚪"
  else
    arrow="🔴"
  fi
  
  RESULT+="$arrow *$sym* — $price ($change)"
  RESULT+=$'\n'
done
echo "$RESULT"

# Save to editions data
ED_DIR="$HOME/.hermes/editions/data/crypto"
mkdir -p "$ED_DIR"
echo "$DATA" | python3 -c "
import sys, json, os, hashlib
from datetime import datetime
data = json.load(sys.stdin)
coins = []
for sym, cid in [('BTC','bitcoin'),('ETH','ethereum'),('SOL','solana'),('TAO','bittensor'),
                  ('TRX','tron'),('BNB','binancecoin'),('DOT','polkadot'),
                  ('MON','monad'),('ROBO','robonomics-network'),('SKY','skale'),
                  ('AAVE','aave'),('ZEC','zcash')]:
    d = data.get(cid, {})
    chg = d.get('usd_24h_change')
    coins.append({'symbol': sym, 'price': d.get('usd', 0) or 0, 'change_24h': chg if chg is not None else 0})
out = {'source': 'Crypto', 'date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 'coins': coins}
with open(os.path.expanduser('$ED_DIR/latest.json'), 'w') as f:
    json.dump(out, f)

# --- Historique : 1 seul point par jour (celui du premier run de la journee) ---
hpath = os.path.expanduser('$ED_DIR/history.json')
try:
    with open(hpath) as f:
        hist = json.load(f)
except Exception:
    hist = {}
today = datetime.now().strftime('%Y-%m-%d')
for c in coins:
    ser = hist.setdefault(c['symbol'], [])
    if not ser or ser[-1].get('date') != today:
        ser.append({'date': today, 'price': c['price']})
        if len(ser) > 400:
            del ser[0:len(ser) - 400]
with open(hpath, 'w') as f:
    json.dump(hist, f)
print('history.json: ' + str(len(hist)) + ' symboles, ' + today)
"