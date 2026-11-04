# Integration iteration / 整合改善

1. Clarify stale evidence and show the actual router decision: the demo prints synthetic candidate revision, eligibility, metric and local approval. This demonstrates policy behavior, not real model quality.
2. Reduce integration friction: Python example handles success, abstention and failure; HTTP example starts a localhost server and calls it. Existing tests passed in a clean Windows Python 3.12.14 environment (46 passed); all four examples ran. HTTP required sandbox escalation for local sockets.
3. Real evidence gap: the Open-Meteo WeatherNext profile abstains with quality comparison required and no approved matching precipitation evidence. WeatherBench Z500 is a different target; see evidence-source-audit.md. No real scores are imported into the example. Additional version-bound deployment-specific precipitation evaluations and compatible datasets are needed to rank real services.
4. Actual terminal screenshot and uploaded social preview remain unresolved: earlier window capture was unavailable, and Chrome file URL access needs user action. The image is labeled a rendered transcript.
5. Three-person user testing, traffic and real-world benefit remain unknown. The five-minute integration target is not measured. External promotion remains draft.
