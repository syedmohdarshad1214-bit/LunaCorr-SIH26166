"""Ten fresh-process offline startup checks plus API report integrity checks.

Run after creating the demonstration experiments. Does not acquire real data.
"""
from pathlib import Path
import http.client
import json
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
results=[]
for index in range(10):
    process=subprocess.Popen([sys.executable,'serve.py','--port','8011'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    started=time.perf_counter()
    try:
        for _ in range(100):
            try:
                c=http.client.HTTPConnection('127.0.0.1',8011,timeout=1);c.request('GET','/api/status');r=c.getresponse();status=json.loads(r.read());c.close()
                if r.status==200:break
            except OSError:pass
            if process.poll() is not None:raise RuntimeError(process.stderr.read().decode())
            time.sleep(.1)
        else:raise RuntimeError('Startup timed out')
        c=http.client.HTTPConnection('127.0.0.1',8011,timeout=2);c.request('GET','/');r=c.getresponse();body=r.read();c.close()
        assert r.status==200 and b'LunaCorr' in body
        c=http.client.HTTPConnection('127.0.0.1',8011,timeout=2);c.request('GET','/api/experiments');r=c.getresponse();runs=json.loads(r.read());c.close()
        assert len(runs)>=4
        results.append({'run':index+1,'status':'PASS','startup_s':time.perf_counter()-started,'saved_experiments':len(runs)})
    finally:
        process.terminate();process.wait(timeout=10)
(ROOT/'backups/restart_checks.json').write_text(json.dumps({'scope':'10 fresh server processes, home page, status and cached experiment discovery; not 10 real science runs','results':results},indent=2)+'\n')
print(json.dumps({'passed':len(results),'report':'backups/restart_checks.json'}))
