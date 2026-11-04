# 貢獻指南

歡迎協助改進 AI Skill Router。請先閱讀 [roadmap](ROADMAP.zh-TW.md)，並透過 issue 描述想要改變的行為。範圍清楚的小型 pull request 較容易審查。

使用 Python 3.11+ 與虛擬環境：

```sh
python -m pip install -e ".[test]" -c constraints-dev.txt
python -m pytest -q
python examples/offline_demo.py
```

測試不得依賴即時外部 API。請標示合成證據，避免將 benchmark 主張套用到不同部署。記錄假設、測試結果及安全影響；不要在 issue 放憑證或私人輸入。可參考 [issue 草稿](outputs/issue-drafts.md)。 [English](CONTRIBUTING.md)

