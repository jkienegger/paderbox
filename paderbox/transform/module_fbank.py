"""
Provides fbank features and the fbank filterbank.
"""

from typing import Optional

from cached_property import cached_property
import numpy as np
import scipy.signal

from paderbox.transform.module_filter import preemphasis_with_offset_compensation
from paderbox.transform.module_stft import stft
from paderbox.transform.module_stft import stft_to_spectrogram


# pylint: disable=too-many-arguments,line-too-long

class MelTransform:
    def __init__(
            self,
            sample_rate: int,
            stft_size: int,
            number_of_filters: int,
            lowest_frequency: Optional[int] = 50,
            highest_frequency: Optional[int] = None,
            log: bool = True,
            eps: float = 1e-18,
            *,
            warping_fn=None,
            independent_axis=0,
    ):
        """
        Transforms linear spectrogram to (log) mel spectrogram.

        Args:
            number_of_filters: number of filters to be applied
            sample_rate: sample rate of audio signal
            stft_size: fft_length used in stft
            lowest_frequency: onset of first filter
            highest_frequency: offset of last filter
            log: apply log to mel spectrogram
            eps:
            warping_fn: function to (randomly) remap fbank center frequencies
            independent_axis: independent axis for which independently warped
                filter banks are used.

        >>> mel_transform = MelTransform(16000, 512, 40)
        >>> spec = np.zeros((3, 1, 100, 257))
        >>> logmelspec = mel_transform(spec)
        >>> logmelspec.shape
        (3, 1, 100, 40)
        >>> rec = mel_transform.inverse(logmelspec)
        >>> rec.shape
        (3, 1, 100, 257)
        >>> from paderbox.utils.random_utils import Uniform
        >>> warping_fn = HzWarping(alpha_sampling_fn=Uniform(low=.9, high=1.1), fhi_ratio_sampling_fn=Uniform(low=.6,high=.7))
        >>> mel_transform = MelTransform(16000, 512, 40, warping_fn=warping_fn)
        >>> mel_transform(spec).shape
        (3, 1, 100, 40)
        >>> mel_transform = MelTransform(16000, 512, 40, warping_fn=warping_fn, independent_axis=(0,1,2))
        >>> mel_transform(spec).shape
        (3, 1, 100, 40)
        """
        self.sample_rate = sample_rate
        self.stft_size = stft_size
        self.number_of_filters = number_of_filters
        self.lowest_frequency = lowest_frequency
        self.highest_frequency = highest_frequency
        self.log = log
        self.eps = eps
        self.warping_fn = warping_fn
        self.independent_axis = [independent_axis] if np.isscalar(independent_axis) else independent_axis

    @cached_property
    def fbanks(self):
        """Create filterbank matrix according to member variables."""
        fbanks = get_fbanks(
            sample_rate=self.sample_rate,
            stft_size=self.stft_size,
            number_of_filters=self.number_of_filters,
            lowest_frequency=self.lowest_frequency,
            highest_frequency=self.highest_frequency,
        )
        fbanks = fbanks / (fbanks.sum(axis=-1, keepdims=True) + self.eps)
        return fbanks.T

    @cached_property
    def ifbanks(self):
        """Create (pseudo)-inverse of filterbank matrix."""
        return np.linalg.pinv(self.fbanks.T).T

    def __call__(self, x):
        if self.warping_fn is None:
            x = x @ self.fbanks
        else:
            independent_axis = [ax if ax >= 0 else x.ndim+ax for ax in self.independent_axis]
            assert all([0 <= ax < x.ndim-1 for ax in independent_axis]), self.independent_axis
            size = [
                x.shape[i] if i in independent_axis else 1
                for i in range(x.ndim-1)
            ]
            fbanks = get_fbanks(
                sample_rate=self.sample_rate,
                stft_size=self.stft_size,
                number_of_filters=self.number_of_filters,
                lowest_frequency=self.lowest_frequency,
                highest_frequency=self.highest_frequency,
                warping_fn=self.warping_fn,
                size=size,
            ).astype(np.float32)
            fbanks = fbanks / (fbanks.sum(axis=-1, keepdims=True) + self.eps)
            fbanks = fbanks.swapaxes(-2, -1)
            # The following is the same as `np.einsum('...F,...FN->...N', x, fbanks)`, but much faster (see https://github.com/fgnt/paderbox/pull/35).
            if fbanks.shape[-3] == 1:
                x = x @ fbanks.squeeze(-3)
            else:
                x = (x[..., None, :] @ fbanks).squeeze(-2)
        if self.log:
            x = np.log(x + self.eps)
        return x

    def inverse(self, x):
        """Invert the mel-filterbank transform."""
        if self.log:
            x = np.exp(x)
        return np.maximum(np.dot(x, self.ifbanks), 0.)


def get_fbanks(
        sample_rate, stft_size, number_of_filters,
        lowest_frequency=0., highest_frequency=None,
        warping_fn=None, size=()
):
    """Computes mel filter banks

    Args:
        sample_rate:
        stft_size:
        number_of_filters: number of mel filter banks
        lowest_frequency: onset frequency of the first filter
        highest_frequency: offset frequency of the last filter
        warping_fn: optional function to warp the filter center frequencies,
            e.g., VTLP (https://www.cs.utoronto.ca/~hinton/absps/perturb.pdf)
        size: size of independent dims in front of filter bank dims, E.g., for
            size=(2,3) returned filterbanks have shape (*size, number_of_filters, fft_length//2+1).
            This is required when different warping is to be applied for
            different independent axis.

    Returns:

    >>> fbanks = get_fbanks(8000, 32, 10)
    >>> fbanks[[0,-1]]
    array([[0.47080041, 0.52919959, 0.        , 0.        , 0.        ,
            0.        , 0.        , 0.        , 0.        , 0.        ,
            0.        , 0.        , 0.        , 0.        , 0.        ,
            0.        , 0.        ],
           [0.        , 0.        , 0.        , 0.        , 0.        ,
            0.        , 0.        , 0.        , 0.        , 0.        ,
            0.        , 0.1996357 , 0.59750853, 0.99538136, 0.66925631,
            0.33462816, 0.        ]])
    >>> get_fbanks(8000, 32, 10, warping_fn=HzWarping(\
            alpha_sampling_fn=lambda size: 0.9+0.2*np.random.rand(*size),\
            fhi_ratio_sampling_fn=lambda n: 0.7,\
        )).shape
    (10, 17)
    >>> get_fbanks(8000, 32, 10, size=(2,3), warping_fn=HzWarping(\
            alpha_sampling_fn=lambda size: 0.9+0.2*np.random.rand(*size),\
            fhi_ratio_sampling_fn=lambda n: 0.7,\
        )).shape
    (2, 3, 10, 17)

    """
    highest_frequency = sample_rate / 2 if highest_frequency is None else highest_frequency
    if highest_frequency < 0:
        highest_frequency = highest_frequency % sample_rate / 2
    f = mel2hz(np.linspace(
        hz2mel(lowest_frequency), hz2mel(highest_frequency), number_of_filters + 2
    ))
    if warping_fn is not None:
        f = warping_fn(f, size=size, max_frequency=sample_rate/2)
    k = hz2bin(f, sample_rate, stft_size)
    centers = k[..., 1:-1, None]
    onsets = np.minimum(k[..., :-2, None], centers - 1)
    offsets = np.maximum(k[..., 2:, None], centers + 1)
    idx = np.arange(stft_size // 2 + 1)
    fbanks = np.maximum(
        np.minimum(
            (idx-onsets)/(centers-onsets),
            (idx-offsets)/(centers-offsets)
        ),
        0
    )
    return np.broadcast_to(fbanks, (*size, *fbanks.shape[-2:]))


def hz2mel(frequency):
    """Convert a value in Hertz to Mel

    Args:
        frequency: a value in Hz. This can also be a numpy array, conversion proceeds
            element-wise.

    Returns: a value in Mels. If an array was passed in, an identical sized
        array is returned.

    """
    return 2595 * np.log10(1 + frequency / 700.0)


def mel2hz(frequency):
    """Convert a value in Mel to Hertz

    Args:
        frequency: a value in Mels. This can also be a numpy array, conversion
            proceeds element-wise.

    Returns: a value in Hz. If an array was passed in, an identical sized
        array is returned.

    """
    return 700 * (10 ** (frequency / 2595.0) - 1)


def bin2hz(fft_bin_index, sample_rate, fft_length):
    """Convert a fft bin to Hz

    Args:
        fft_bin_index: fft bin index. This can also be a numpy array,
            conversion proceeds element-wise.
        sample_rate:
        fft_length:

    Returns:

    """
    return sample_rate * fft_bin_index / fft_length


def hz2bin(frequency, sample_rate, fft_length):
    """Convert Hz to fft bin idx (soft, i.e. return value is a float not an int)

    Args:
        frequency: a value in Hz. This can also be a numpy array, conversion
            proceeds element-wise.
        sample_rate:
        fft_length:

    Returns:

    """
    return frequency * fft_length / sample_rate


def hz_warping(frequency, alpha, fhi_ratio, max_frequency=None):
    """Performs piece wise linear warping of frequencies [Hz].
    http://www.cs.toronto.edu/~ndjaitly/jaitly-icml13.pdf

    Args:
        frequency: frequency vector in Hz
        alpha: scalar or array of alphas
        fhi_ratio: scalar or array of ratios \in [0,1] such that
            fhi = fhi_ratio * sample_rate/2
        max_frequency:

    Returns:

    >>> sample_rate = 16000
    >>> lowest_frequency = 0
    >>> highest_frequency = sample_rate/2
    >>> number_of_filters = 10
    >>> alpha_max = 1.2
    >>> frequency = mel2hz(np.linspace(hz2mel(lowest_frequency), hz2mel(highest_frequency), number_of_filters+2))
    >>> frequency
    array([   0.        ,  180.21928115,  406.83711843,  691.7991039 ,
           1050.12629534, 1500.70701371, 2067.29249375, 2779.74887082,
           3675.63149949, 4802.16459006, 6218.73051459, 8000.        ])
    >>> f_warped = hz_warping(frequency, alpha=1.1, fhi_ratio=.6)
    >>> f_warped
    array([   0.        ,  198.24120926,  447.52083027,  760.97901429,
           1155.13892487, 1650.77771509, 2274.02174313, 3057.7237579 ,
           4043.19464944, 5185.90483925, 6432.48285284, 8000.        ])
    >>> f_warped = hz_warping(frequency, alpha=[.9, 1.1], fhi_ratio=.6)
    >>> f_warped
    array([[   0.        ,  162.19735303,  366.15340659,  622.61919351,
             945.11366581, 1350.63631234, 1860.56324438, 2501.77398374,
            3308.06834954, 4322.48927857, 5951.54009178, 8000.        ],
           [   0.        ,  198.24120926,  447.52083027,  760.97901429,
            1155.13892487, 1650.77771509, 2274.02174313, 3057.7237579 ,
            4043.19464944, 5185.90483925, 6432.48285284, 8000.        ]])
    >>> f_warped/frequency
    array([[       nan, 0.9       , 0.9       , 0.9       , 0.9       ,
            0.9       , 0.9       , 0.9       , 0.9       , 0.90011269,
            0.95703457, 1.        ],
           [       nan, 1.1       , 1.1       , 1.1       , 1.1       ,
            1.1       , 1.1       , 1.1       , 1.1       , 1.07990985,
            1.03437234, 1.        ]])
    >>> hz_warping(frequency, alpha=[[.9], [1.1]], fhi_ratio=.75).shape
    (2, 1, 12)
    """
    if max_frequency is None:
        max_frequency = frequency[-1]
    assert (np.max(frequency) - max_frequency) < 1e-6, (np.max(frequency), max_frequency)
    alpha = np.array(alpha)
    fhi = np.array(fhi_ratio * max_frequency)
    breakpoints = fhi * np.minimum(alpha, 1) / alpha

    if breakpoints.ndim == 0:
        breakpoints = np.array(breakpoints)
    breakpoints[(breakpoints > max_frequency) + ((alpha * breakpoints) > max_frequency)] = max_frequency
    bp_value = alpha * breakpoints

    frequency, breakpoints, bp_value = np.broadcast_arrays(
        frequency, breakpoints[..., None], bp_value[..., None]
    )
    f_warped = alpha[..., None] * frequency
    idx = frequency > breakpoints
    f_warped[idx] = (
            max_frequency
            + (
                    (frequency[idx] - max_frequency)
                    * (max_frequency - bp_value[idx]) / (max_frequency - breakpoints[idx])
        )
    )
    return f_warped


def mel_warping(frequency, alpha, fhi_ratio, max_frequency=None):
    """Transforms frequency to Mel domain and performs piecewise linear warping
    there. Finally transforms warped frequency back to Hz.

    Args:
        frequency:
        alpha:
        fhi_ratio:
        max_frequency:

    Returns:

    """
    frequency = hz2mel(frequency)
    if max_frequency is not None:
        max_frequency = hz2mel(max_frequency)
    frequency = hz_warping(frequency, alpha, fhi_ratio, max_frequency)
    return mel2hz(frequency)


class HzWarping:
    """
    >>> sample_rate = 16000
    >>> lowest_frequency = 0
    >>> highest_frequency = sample_rate/2
    >>> number_of_filters = 10
    >>> f = mel2hz(np.linspace(hz2mel(lowest_frequency), hz2mel(highest_frequency), number_of_filters+2))
    >>> from paderbox.utils.random_utils import Uniform
    >>> warping_fn = HzWarping(alpha_sampling_fn=Uniform(low=.9, high=1.1), fhi_ratio_sampling_fn=Uniform(low=.6,high=.7))
    >>> np.random.seed(0)
    >>> warping_fn(f)/f
    array([      nan, 1.0097627, 1.0097627, 1.0097627, 1.0097627, 1.0097627,
           1.0097627, 1.0097627, 1.0097627, 1.0097627, 1.0055517, 1.       ])
    >>> np.random.seed(1)
    >>> warping_fn(f)/f
    array([       nan, 0.9834044 , 0.9834044 , 0.9834044 , 0.9834044 ,
           0.9834044 , 0.9834044 , 0.9834044 , 0.9834044 , 0.9834044 ,
           0.99025952, 1.        ])
    """
    def __init__(self, alpha_sampling_fn, fhi_ratio_sampling_fn):
        self.alpha_sampling_fn = alpha_sampling_fn
        self.fhi_ratio_sampling_fn = fhi_ratio_sampling_fn

    def __call__(self, frequency, size=(), max_frequency=None):
        return hz_warping(
            frequency,
            alpha=self.alpha_sampling_fn(size),
            fhi_ratio=self.fhi_ratio_sampling_fn(size),
            max_frequency=max_frequency,
        )


class MelWarping(HzWarping):
    def __call__(self, frequency, size=(), max_frequency=None):
        return mel_warping(
            frequency,
            alpha=self.alpha_sampling_fn(size),
            fhi_ratio=self.fhi_ratio_sampling_fn(size),
            max_frequency=max_frequency,
        )


def fbank(time_signal, sample_rate=16000, window_length=400, stft_shift=160,
          number_of_filters=23, stft_size=512, lowest_frequency=0,
          highest_frequency=None, preemphasis_factor=0.97,
          window=scipy.signal.windows.hamming, denoise=False):
    """
    Compute Mel-filterbank energy features from an audio signal.

    Source: https://github.com/jameslyons/python_speech_features
    Tutorial: http://www.practicalcryptography.com/miscellaneous/machine-learning/guide-mel-frequency-cepstral-coefficients-mfccs/ # noqa

    Illustrations: http://ntjenkins.upb.de/view/PythonToolbox/job/python_toolbox_notebooks/HTML_Report/toolbox_examples/transform/06%20-%20Additional%20features.html

    Args:
        time_signal: the audio signal from which to compute features.
            Should be an N*1 array
        sample_rate: the sample rate of the signal we are working with.
        window_length: the length of the analysis window in samples.
            Default is 400 (25 milliseconds @ 16kHz)
        stft_shift: the step between successive windows in samples.
            Default is 160 (10 milliseconds @ 16kHz)
        number_of_filters: the number of filters in the filterbank, default 23.
        stft_size: the FFT size. Default is 512.
        lowest_frequency: lowest band edge of mel filters.
            In Hz, default is 0.
        highest_frequency: highest band edge of mel filters.
            In Hz, default is samplerate/2
        preemphasis_factor: apply preemphasis filter with preemph as coefficient.
            0 is no filter. Default is 0.97.
        window: window function used for stft
        denoise:

    Returns: A numpy array of size (frames by number_of_filters) containing the
        Mel filterbank features.

    """
    highest_frequency = highest_frequency or sample_rate / 2
    time_signal = preemphasis_with_offset_compensation(
        time_signal, preemphasis_factor)

    stft_signal = stft(
        time_signal,
        size=stft_size, shift=stft_shift,
        window=window, window_length=window_length,
        fading=None
    )

    spectrogram = stft_to_spectrogram(stft_signal) / stft_size

    mel_transform = MelTransform(
        sample_rate=sample_rate,
        stft_size=stft_size,
        number_of_filters=number_of_filters,
        lowest_frequency=lowest_frequency,
        highest_frequency=highest_frequency,
        log=False
    )
    feature = mel_transform(spectrogram)

    if denoise:
        feature -= np.min(feature, axis=0)

    return feature


def logfbank(time_signal, sample_rate=16000, window_length=400, stft_shift=160,
             number_of_filters=23, stft_size=512, lowest_frequency=0,
             highest_frequency=None, preemphasis_factor=0.97,
             window=scipy.signal.windows.hamming, denoise=False, eps=1e-18):
    """Generates log fbank features from time signal.

    Simply wraps fbank function. See parameters there.
    """
    return np.log(
        fbank(
            time_signal,
            sample_rate=sample_rate,
            window_length=window_length,
            stft_shift=stft_shift,
            number_of_filters=number_of_filters,
            stft_size=stft_size,
            lowest_frequency=lowest_frequency,
            highest_frequency=highest_frequency,
            preemphasis_factor=preemphasis_factor,
            window=window,
            denoise=denoise
        ) + eps
    )
