"""Reuse guarded real-call verification; keep this recovery's evidence separate."""
import importlib.util
import json
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
VIDEO=OUT.parent/'workflow-logging/video'
sys.path.insert(0,str(VIDEO))
import watch_summary_import
watch_summary_import.OUT=OUT
spec=importlib.util.spec_from_file_location('live_validation',VIDEO/'verify-real.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.OUT=OUT;module.STATE=OUT/'real-results.json'
module.report=json.loads(module.STATE.read_text()) if module.STATE.exists() else {}
{'analysis':module.analysis,'generation':module.generation}[sys.argv[1]]()
