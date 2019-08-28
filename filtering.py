from scipy.signal import butter, lfilter, lfilter_zi

class Filter:
    def __init__(self, cutOff, fs, order=3):
        b, a = Filter.butter_lowpass(cutOff, fs, order= order)
        self.a = a
        self.b = b

    @staticmethod
    def butter_lowpass(cutOff, fs, order=3):
        """
        Generates Butterworth coefficients in based on the set of given parameters:
            cutOff: desired cut-off frequency
            fs: sampling frequency
            order: desired order of the filter

        Filter type is discrete lowpass
        """
        nyq = 0.5 *fs
        normal_cutOff = cutOff/nyq
        b, a = butter(order, normal_cutOff, btype='low', analog=False)
        return b, a

    def butter_lowpass_filter(self, data):
        """
        Implements digital butterworth lowpass filter.
        Assumes 1-D array_like type.
        """
        y = lfilter(self.b, self.a, data, zi=lfilter_zi(b, a)*data[0])[0]
        return y
