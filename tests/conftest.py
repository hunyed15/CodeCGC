import sys
from pathlib import Path

# Add scripts directory to Python path for imports
WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE / "scripts"))
sys.path.insert(0, str(WORKSPACE / "codecgcmcp" / "src"))
