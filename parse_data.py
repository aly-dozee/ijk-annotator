import glob
import os
import pandas as pd
import numpy as np
from scipy.signal import butter, sosfiltfilt
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

from doz_file_utils import compose_doz, parse_doz
from doz_file_utils.doz_dataclasses import ParsedDOZ

def _parse_single_file(file_path):
    """
    Worker function for parsing a single DOZ file. 
    Returns a dict {ts, gain, signals}.
    """
    try:
        with open(file_path, "rb") as doz_file:
            doz_data = doz_file.read()
            parsed_doz = parse_doz(doz_data, accept_multiple_timestamps=True)

        ts = int(parsed_doz.timestamp.timestamp())
        gain = parsed_doz.primary_sheet.gain
        data = parsed_doz.primary_sheet.data

        # print(f"Processed file: {file_path.split('/')}")

        return {"ts": ts, "gain": gain, "signals": data}

    except Exception as e:
        # Return None to signal an error, or raise if you prefer to fail fast
        print(f"Error processing {file_path}: {repr(e)}")
        return None


def parse_binary_file(path_to_file, duration):
    """
    Parse DOZ files under 'path_to_file' (recursively), returning a list of dicts:
      [
        {"ts": <int>, "gain": <float>, "signals": <list or array>},
        ...
      ]
    'duration' is currently unused here but included for API compatibility.
    """

    # Gather all files (not directories) recursively
    all_paths = glob.glob(os.path.join(path_to_file, "**/*"), recursive=True)
    file_paths = [p for p in all_paths if os.path.isfile(p)]

    # Use ThreadPoolExecutor for parallel parsing
    results = []
    with ThreadPoolExecutor() as executor:
        # Map files to the parser function in parallel, show progress via tqdm
        futures = executor.map(_parse_single_file, file_paths)

        for parsed in tqdm(futures, desc="Parsing DOZ files", total=len(file_paths)):
            if parsed is not None:
                results.append(parsed)

    return results


def sos_filter(piezo, order=2, frequency_list=None, sample_rate=250):
    """
    Apply Butterworth bandpass filter with SOS output for a given input signal.

    Parameters:
        piezo (array-like): 1D signal to which Butterworth bandpass needs to be applied.
        order (int): Order of the filter.
        frequency_list (list): List containing two elements [lowcut, highcut] frequencies for the bandpass.
        sample_rate (int): Sampling frequency of the signal.

    Returns:
        filtered (array-like): Filtered signal after applying the Butterworth bandpass.
    """
    if frequency_list is None or not isinstance(frequency_list, list) or len(frequency_list) != 2:
        raise ValueError("frequency_list must be a list with two elements [lowcut, highcut].")

    def butter_bandpass(lowcut, highcut, sampling_rate, order_bb):
        nyq = 0.5 * sampling_rate
        low = lowcut / nyq
        high = highcut / nyq
        sos_bb = butter(order_bb, [low, high], btype='band', output='sos')
        return sos_bb

    sos = butter_bandpass(frequency_list[0], frequency_list[1], sample_rate, order_bb=order)
    filtered = sosfiltfilt(sos, piezo)
    return filtered
