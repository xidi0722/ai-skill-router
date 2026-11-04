# Developer onboarding verification

Checked 2026-11-04. The repository started clean at `fe4c3e0`, matching `origin/main` at that time. Project changes were pushed as `2b0b14c`; repository settings and contribution issues were subsequently updated. External community posts remain drafts.

## Positioning

Use **AI Skill Router** as the display name to match the repository. Retain `universal-model-router` as the Python distribution and `umr` CLI to avoid breaking existing installation commands. Agent developers and scientific-tool integrators can inspect eligibility, evidence compatibility and abstention; this is an early prototype with no validated real-world ranking advantage.

## Actual checks

- Integration iteration, 2026-11-04 UTC: a new Python 3.12.14 Windows venv created without pip was installed using a separate pip `--python` invocation; `pytest -q` returned 46 passed. `offline_demo.py`, `python_integration.py`, `http_integration.py` and `weather_evidence_gap.py` succeeded. Localhost TCP required execution outside the restricted sandbox. CI for this iteration must be checked on its actual commit.

- Rechecked this phase in a new Windows 11 / Python 3.12.14 venv: `pip install -e '.[test]' -c constraints-dev.txt`, `pytest -q` (46 passed), and the offline demo all completed. The bundled runtime required a separate pip bootstrap before the documented install command.
- Two attempts to launch the actual demo in a visible terminal did not yield a targetable terminal window in the computer-use window inventory. The repository therefore retains the clearly labeled rendered stdout image; no genuine terminal screenshot or recording is claimed.

- Windows 11, Python 3.12.14: existing venv regression test suite, `python -m pytest -q`, **46 passed**.
- Created a fresh venv using the bundled interpreter with `--without-pip`, bootstrapped pip 26.2.2, then ran its `python -m pip install -e .` with no preinstalled project dependencies. The install and `python examples/offline_demo.py` completed successfully. The standard `python -m venv` bootstrap itself could not be tested here because the bundled runtime lacks `ensurepip`.
- The demo returned `-2` and `2` with substitution checks, selected synthetic `fixture-a`, and abstained after a revision change. Exact captured stdout: [demo-transcript.txt](demo-transcript.txt).
- `assets/demo-transcript.png` is a **rendering of that captured output**, not a screenshot or recording of a terminal. A genuine screen capture or recording remains to be made before claiming one in promotional material.
- `assets/social-preview.png` is 1280×640 and 25,322 bytes. Upload was blocked because the Chrome extension does not have “Allow access to file URLs” enabled; it has not been uploaded as the GitHub social preview.
- [GitHub Actions run 41841204321](https://github.com/xidi0722/ai-skill-router/actions/runs/41841204321) succeeded for `2b0b14c` on Windows and Ubuntu with Python 3.11 and 3.12, including install, tests and offline demo. macOS remains unverified.
- Four contribution issues were created: [#1](https://github.com/xidi0722/ai-skill-router/issues/1), [#2](https://github.com/xidi0722/ai-skill-router/issues/2), [#3](https://github.com/xidi0722/ai-skill-router/issues/3), and [#4](https://github.com/xidi0722/ai-skill-router/issues/4). Traffic views/clones and independent cold-start user results are unknown.

The offline demo uses synthetic candidates, metrics and locally supplied approvals. It cannot establish model accuracy or validate a third-party forecast. The unsigned local approval ledger is not an authenticated trust service.

## Reproduce

From a standard Python 3.11+ environment:

```sh
python -m pip install -e ".[test]" -c constraints-dev.txt
python -m pytest -q
python examples/offline_demo.py
```

To regenerate the two PNG files from a real execution, install Pillow and run `python tools/create_presentation_assets.py`. That tool renders stdout and labels the result as a rendering.

繁體中文：本次在 Windows 11、Python 3.12.14 驗證；全套測試 46 通過。新隔離環境先以外部 pip bootstrap，再執行 README 的 editable 安裝與 Demo，皆成功。遠端 CI 的 Windows／Ubuntu 與 Python 3.11／3.12 組合均通過；macOS 未驗證。圖像為真實 stdout 的繪製版，並非實際螢幕截圖。社群推廣內容維持草稿。
