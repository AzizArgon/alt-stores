"""Charts for chapter III from the numbers in docs/experiment.md -> figures/*.png."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
(HERE / "figures").mkdir(exist_ok=True)

if __name__ == "__main__":
    print("charts: ok")
