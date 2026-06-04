"""Tests need a trained model + metadata. Build them from the committed CSV if
they're missing, before the app modules are imported."""

import os
import subprocess
import sys

if not os.path.exists(os.environ.get("MODEL_PATH", "model/model.pkl")):
    subprocess.run([sys.executable, "-m", "app.train"], check=True)
