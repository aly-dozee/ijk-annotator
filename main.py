import sys
import argparse
import pandas as pd
import dash
import warnings

from layout import create_layout
from callbacks import register_callbacks

warnings.simplefilter("ignore", category=UserWarning)

def parse_parquet_file(filepath, ecg_flag=False):
    """
    Read a parquet file that must have columns:
      - 'ts' (int or float) → Timestamp
      - 'gain' (float or int) → Gain multiplier
      - 'signals' (array of ints, shape=(30000,), dtype=uint16) → Signal data

    If 'ecg_flag' is True, we also require 'ecg_signal'.

    Returns:
      List of dictionaries with the structure:
        [
          {"ts": <timestamp>, "gain": <gain>, "signals": <array_of_ints>},
          ...
        ]
    """
    try:
        df = pd.read_parquet(filepath)
    except Exception as e:
        print(f"Error reading parquet file: {e}")
        sys.exit(1)

    required_cols = {"ts", "gain", "signals"}
    missing_cols = required_cols - set(df.columns)

    if missing_cols:
        print(f"Error: Parquet file is missing required column(s): {missing_cols}")
        sys.exit(1)

    if ecg_flag and "ecg_signal" not in df.columns:
        print("Error: ECG flag specified, but 'ecg_signal' column not found.")
        sys.exit(1)

    # Ensure signals are lists
    df["signals"] = df["signals"].apply(lambda x: list(x) if isinstance(x, (list, tuple)) else x)

    # Flip signals around the normalized range if gain is odd
    def flip_signal(row):
        if row["gain"] % 2 == 1:  # Check if gain is odd
            signal = row["signals"]
            min_val, max_val = min(signal), max(signal)
            if min_val == max_val:
                return signal  # Avoid division by zero
            
            # Normalize to [0, 1]
            normalized = [(s - min_val) / (max_val - min_val) for s in signal]

            # Flip around 0.5 and rescale
            flipped = [1 - s for s in normalized]
            rescaled = [s * (max_val - min_val) + min_val for s in flipped]

            return rescaled
        return row["signals"]

    df["signals"] = df.apply(flip_signal, axis=1)

    signals_data = df.to_dict(orient="records")
    # print(f"signals @ row 0:\n{signals_data[0]}")
    return signals_data


def main():
    """Main entry point for the Signal Annotator."""
    parser = argparse.ArgumentParser(description="Run the Signal Annotator")
    parser.add_argument("duration", type=int, help="Duration in seconds for signal spread")
    parser.add_argument("parquet_path", type=str, help="Path to the parquet file")
    parser.add_argument("-ecg", action="store_true", help="Include ECG data if available")

    args = parser.parse_args()

    # Parse signals from the parquet file
    signals_data = parse_parquet_file(args.parquet_path, ecg_flag=args.ecg)

    # Initialize Dash app
    app = dash.Dash(__name__, suppress_callback_exceptions=True)
    app.title = "Signal Annotator"

    # Set up layout with parsed data
    app.layout = create_layout(signals_data, args.parquet_path)

    # Register callbacks
    register_callbacks(app, signals_data, args.duration)

    # Run Dash server
    app.run_server(debug=True, threaded=True)


if __name__ == "__main__":
    main()
