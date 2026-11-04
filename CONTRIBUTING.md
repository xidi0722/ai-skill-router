# Contributing

Thanks for helping improve AI Skill Router. Start with the [roadmap](ROADMAP.md) and open an issue describing the behavior you want to change. Small, focused pull requests are easier to review.

Use Python 3.11+ in a virtual environment:

```sh
python -m pip install -e ".[test]" -c constraints-dev.txt
python -m pytest -q
python examples/offline_demo.py
```

Tests must not depend on live external APIs. Mark synthetic evidence and avoid copying benchmark claims to a different deployment. Document assumptions, test results and security consequences. Do not include credentials or private input data in issues. For an entry point see [issue drafts](outputs/issue-drafts.md).

繁體中文：請先描述預期行為，使用本機 fixture 或 mock 測試，並清楚標示合成證據與未驗證限制。

