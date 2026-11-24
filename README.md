# Document Review Queue

Route a synthetic field extraction to a reviewer, record the outcome, and reject a stale second decision.

[Source](project.py) · [Demo evidence](evidence/demo.json) · [Verification](evidence/checks.json)

## Run locally

Requires Python 3.11+.

```sh
python project.py
python -m unittest discover -v
```

## Engineering decision

Confidence alone cannot clear an item. Track supporting evidence, validation, version, and reviewer identity on the final decision.

Local workflow with authored OCR observations. The demo does not make real eligibility or payment decisions.



[Technology or project reference](https://docs.python.org/3/library/sqlite3.html)
