# 收件證據 PoC(隔離測試分支,不是正式流程)

這個分支只用來試 Sigstore 收件證據(Astra v0.7.7 §五建議)。`poc/ledger.txt` 是代替帳本的假資料;
每次 push 都會觸發 `.github/workflows/attest-poc.yml`,證據存到 `attest-poc-evidence` 分支。
正式帳本 astra-ledger、main 的網站與排程都沒有改。
