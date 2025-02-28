import pandas as pd
import numpy as np
from scipy.signal import butter, sosfiltfilt

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
