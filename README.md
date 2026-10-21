# 收件證據鏈（PoC；隔離測試分支，不是正式流程）

這個分支只由 `attest-poc` 分支上的 workflow（`.github/workflows/attest-poc.yml`）寫入。每次 push 到 `attest-poc`，workflow 會：

1. 對那次 push 的確切 commit 做一份收件清單 `att/<序號>_<commit>.manifest.json`：repo 名稱與數字 ID、分支、事件、commit、tree、每個檔的 SHA-256、這次 push 之前的分支頭、**上一個證據 commit**（`evidence_parent`）
2. 用 GitHub OIDC + Sigstore 簽章（`actions/attest`），完整 bundle 存成 `att/<序號>_<commit>.bundle.json`
3. 當下的 Sigstore 信任根快照存進 `trust/`（內容有變才新增，舊的保留；驗證程式另外用 sigstore/root-signing 的版本核對，不單靠這裡的檔）

每個證據 commit 只新增這一筆；清單裡的 `evidence_parent` = 上一個證據 commit → 形成一條只能往後接的鏈。

離線驗證程式：main 的 `research/ledger_v3_draft_2026-10-16/v3_attest.py`。
