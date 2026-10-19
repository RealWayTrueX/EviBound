"""Runs the demo engine cross-check as part of the standard `discover -s tests` run.

Skips (visibly) when node is not installed. The real test lives in
demo/tests/test_demo_engine.py; see demo/README.md.
"""

from demo.tests.test_demo_engine import DemoEngineMatchesPython  # noqa: F401
