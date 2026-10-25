"""Download Metrica Sports' public sample games into data/raw/.

Source: https://github.com/metrica-sports/sample-data
Games 1 and 2 are CSV files (one per team plus events); game 3 uses the
EPTS format (tracking .txt + metadata .xml) with JSON events.

Usage:
    python scripts/download_data.py            # all three games
    python scripts/download_data.py --games 1 2
"""
import argparse
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/metrica-sports/sample-data/master/data"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

FILES = {
    1: [
        "Sample_Game_1_RawEventsData.csv",
        "Sample_Game_1_RawTrackingData_Home_Team.csv",
        "Sample_Game_1_RawTrackingData_Away_Team.csv",
    ],
    2: [
        "Sample_Game_2_RawEventsData.csv",
        "Sample_Game_2_RawTrackingData_Home_Team.csv",
        "Sample_Game_2_RawTrackingData_Away_Team.csv",
    ],
    3: [
        "Sample_Game_3_events.json",
        "Sample_Game_3_metadata.xml",
        "Sample_Game_3_tracking.txt",
    ],
}


def download_game(game: int, overwrite: bool = False) -> None:
    game_dir = RAW_DIR / f"Sample_Game_{game}"
    game_dir.mkdir(parents=True, exist_ok=True)
    for name in FILES[game]:
        target = game_dir / name
        if target.exists() and not overwrite:
            print(f"skip   {target.relative_to(RAW_DIR)} (already present)")
            continue
        url = f"{BASE_URL}/Sample_Game_{game}/{name}"
        print(f"fetch  {url}")
        urllib.request.urlretrieve(url, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--games", type=int, nargs="+", default=[1, 2, 3], choices=[1, 2, 3])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for game in args.games:
        download_game(game, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
