import sys
import argparse
import pandas as pd
import dash
import warnings
import dash_bootstrap_components as dbc

from layout import create_layout
from callbacks import register_callbacks

warnings.simplefilter("ignore", category=UserWarning)

def parse_parquet_file(filepath, ecg_flag=False):
    """
    Read a parquet file that must have columns:
      - 'ts' (int or float) → Timestamp
      - 'gain' (float or int) → Gain multiplier
      - 'signals' (array of ints or floats, shape=(N,)) → Signal data

    If 'ecg_flag' is True, we also require 'ecg_signal'.

    Returns:
      List of dictionaries. Each entry is something like:
        {
          "ts": <timestamp>,
          "gain": <gain>,
          "signals": <list_of_floats>,
          # possibly "ecg_signal": ...
        }
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

    # Ensure signals is a list rather than a numpy array or something else
    df["signals"] = df["signals"].apply(
        lambda x: list(x) if isinstance(x, (list, tuple)) else x
    )

    def flip_signal(row):
        """
        Always normalize the signal to [0,1],
        then only flip it if gain is odd,
        then rescale back to the original min/max range.
        """
        signals = row["signals"]
        if len(signals) == 0:  # in case it's empty
            return signals

        min_val = min(signals)
        max_val = max(signals)
        if min_val == max_val:
            # Avoid division by zero if the signal is a constant
            return signals

        # 1) Normalize to [0, 1]
        normalized = [(s - min_val) / (max_val - min_val) for s in signals]

        # 2) If gain is odd, flip around 0.5
        if row["gain"] % 2 == 1:
            # Flip around 0.5 by doing `1 - x`
            final_data = [1 - s for s in normalized]
        else:
            final_data = normalized

        # 3) Rescale back to [min_val, max_val]
        rescaled = [(s * (max_val - min_val)) + min_val for s in final_data]
        return rescaled

    # Apply flip_signal to every row
    df["signals"] = df.apply(flip_signal, axis=1)

    # Convert DataFrame rows to a list of dict records
    signals_data = df.to_dict(orient="records")
    return signals_data


def main():
    """Main entry point for the Signal Annotator."""
    parser = argparse.ArgumentParser(description="Run the Signal Annotator")
    parser.add_argument("duration", type=int, help="Duration in seconds for signal spread")
    parser.add_argument("parquet_path", type=str, help="Path to the parquet file")

    args = parser.parse_args()

    # Parse signals from the parquet file
    signals_data = parse_parquet_file(args.parquet_path)

    # Initialize Dash app
    app = dash.Dash(__name__, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.SLATE])
    app.title = "Signal Annotator"

    # Set up layout with parsed data
    app.layout = create_layout(signals_data, args.parquet_path)

    # Register callbacks
    register_callbacks(app, signals_data, args.duration)

    # Run Dash server
    app.run_server(debug=True, threaded=True)


if __name__ == "__main__":
    main()
