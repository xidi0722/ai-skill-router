# Developer onboarding verification

Checked 2026-11-04. The repository started clean at `fe4c3e0`, matching `origin/main` at that time. This phase changes local files only; no repository settings, posts or releases were published.

## Positioning

Use **AI Skill Router** as the display name to match the repository. Retain `universal-model-router` as the Python distribution and `umr` CLI to avoid breaking existing installation commands. Agent developers and scientific-tool integrators can inspect eligibility, evidence compatibility and abstention; this is an early prototype with no validated real-world ranking advantage.

## Actual checks

- Rechecked this phase in a new Windows 11 / Python 3.12.14 venv: `pip install -e '.[test]' -c constraints-dev.txt`, `pytest -q` (46 passed), and the offline demo all completed. The bundled runtime required a separate pip bootstrap before the documented install command.
- Two attempts to launch the actual demo in a visible terminal did not yield a targetable terminal window in the computer-use window inventory. The repository therefore retains the clearly labeled rendered stdout image; no genuine terminal screenshot or recording is claimed.

- Windows 11, Python 3.12.14: existing venv regression test suite, `python -m pytest -q`, **46 passed**.
- Created a fresh venv using the bundled interpreter with `--without-pip`, bootstrapped pip 26.2.2, then ran its `python -m pip install -e .` with no preinstalled project dependencies. The install and `python examples/offline_demo.py` completed successfully. The standard `python -m venv` bootstrap itself could not be tested here because the bundled runtime lacks `ensurepip`.
- The demo returned `-2` and `2` with substitution checks, selected synthetic `fixture-a`, and abstained after a revision change. Exact captured stdout: [demo-transcript.txt](demo-transcript.txt).
- `assets/demo-transcript.png` is a **rendering of that captured output**, not a screenshot or recording of a terminal. A genuine screen capture or recording remains to be made before claiming one in promotional material.
- `assets/social-preview.png` is 1280×640 and 25,322 bytes. It has not been uploaded as the GitHub social preview.
- The new GitHub Actions workflow is present locally; no remote workflow run has been performed. Linux, macOS and other Python versions remain unverified in this phase. No CI success badge was added.
- GitHub repository API returned 0 stars, 0 forks and 0 open issues on 2026-11-04. Traffic views/clones and independent cold-start user results are unknown.

The offline demo uses synthetic candidates, metrics and locally supplied approvals. It cannot establish model accuracy or validate a third-party forecast. The unsigned local approval ledger is not an authenticated trust service.

## Reproduce

From a standard Python 3.11+ environment:

```sh
python -m pip install -e ".[test]" -c constraints-dev.txt
python -m pytest -q
python examples/offline_demo.py
```

To regenerate the two PNG files from a real execution, install Pillow and run `python tools/create_presentation_assets.py`. That tool renders stdout and labels the result as a rendering.

繁體中文：本次在 Windows 11、Python 3.12.14 驗證；全套測試 46 通過。新隔離環境先以外部 pip bootstrap，再執行 README 的 editable 安裝與 Demo，皆成功。圖像為真實 stdout 的繪製版，並非實際螢幕截圖；Linux／macOS 與遠端 CI 尚未驗證。推廣內容、repository 設定和 release 皆為草稿。
