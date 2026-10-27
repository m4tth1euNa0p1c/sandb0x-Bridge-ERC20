#!/usr/bin/env bash
# Sonde locale du profil Besu 31339, sans dépendance curl ni clé.
set -euo pipefail

if [[ "${1:-}" != "--probe" ]]; then
  exec timeout 3s /bin/bash "$0" --probe
fi

exec 3<>/dev/tcp/127.0.0.1/8545
request='{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
printf 'POST / HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: %s\r\n\r\n%s' "${#request}" "$request" >&3
IFS= read -r status <&3
[[ "$status" == $'HTTP/1.1 200 OK\r' || "$status" == $'HTTP/1.0 200 OK\r' ]]
response=$(cat <&3)
exec 3<&-
exec 3>&-

# La petite réponse Besu épinglée tient sur une ligne, même en HTTP chunked.
# Reconnaissance stricte: une erreur RPC ou une autre chaîne échoue.
matches=0
while IFS= read -r line; do
  compact=${line//[[:space:]]/}
  if [[ "$compact" == '{"jsonrpc":"2.0","id":1,"result":"0x7a6b"}' ]]; then
    matches=$((matches + 1))
  elif [[ "$compact" == *'"jsonrpc"'* || "$compact" == *'"error"'* ]]; then
    exit 1
  fi
done <<< "$response"
[[ "$matches" == 1 ]]
