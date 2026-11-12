#!/bin/bash
# 依序下載 SEC Financial Statement Data Sets(聯絡方式只從本機檔案讀進請求標頭,不印出)
S=$1; UA=$(cat $S/w8/.sec_ua)
while read -r u; do
  fn=$S/ern/zips/$(basename "$u")
  [ -s "$fn" ] && continue
  for k in 1 2 3; do
    if curl -sS -f -m 900 -A "$UA" -o "$fn.part" "https://www.sec.gov$u"; then mv "$fn.part" "$fn"; echo "ok $(basename "$u") $(stat -c %s "$fn")"; break; fi
    echo "retry $k $(basename "$u")"; sleep 10
  done
  sleep 1
done < ${2:-$S/ern/zips.txt}
echo done
