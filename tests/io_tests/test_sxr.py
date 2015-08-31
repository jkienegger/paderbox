import numpy
import numpy.testing as nptest
from nt.evaluation.sxr import input_sxr, output_sxr
import unittest
from nt.testing import condition


class InputSXRTest(unittest.TestCase):

    @condition.retry(10)
    def test_for_single_input(self):
        expected_snr = numpy.array(10)
        size = (10000, 1, 1)
        x = numpy.random.normal(0, 1, size)
        noise = 10**(-expected_snr/20) * numpy.random.normal(0, 1, size)

        SDR, SIR, SNR = input_sxr(x, noise)

        nptest.assert_almost_equal(SDR, expected_snr, decimal=1)
        self.assertTrue(numpy.isinf(SIR))
        nptest.assert_almost_equal(SNR, expected_snr, decimal=1)

    @condition.retry(10)
    def test_two_inputs_no_noise_no_average(self):
        expected_sir = numpy.array(10)
        size = (10000, 1, 2)
        x = numpy.random.normal(0, 1, size)
        x[:, 0, 0] *= 10**(expected_sir/20)
        noise = numpy.zeros((10000, 1, 1))

        SDR, SIR, SNR = input_sxr(x, noise, average_sources=False)

        expected_result = numpy.array([expected_sir, -expected_sir])
        nptest.assert_almost_equal(SDR, expected_result, decimal=1)
        nptest.assert_almost_equal(SIR, expected_result, decimal=1)
        self.assertTrue(numpy.isinf(SNR).all())

    @condition.retry(10)
    def test_two_different_inputs_no_noise(self):
        expected_sir = numpy.array(10)
        size = (10000, 1, 2)
        x = numpy.random.normal(0, 1, size)
        x[:, 0, 0] *= 10**(expected_sir/20)
        noise = numpy.zeros((10000, 1, 1))

        SDR, SIR, SNR = input_sxr(x, noise)

        expected_result = numpy.array(0)
        nptest.assert_almost_equal(SDR, expected_result, decimal=1)
        nptest.assert_almost_equal(SIR, expected_result, decimal=1)
        self.assertTrue(numpy.isinf(SNR).all())

    @condition.retry(10)
    def test_two_equal_inputs_equal_noise(self):
        size = (10000, 1, 2)
        x = numpy.random.normal(0, 1, size)
        noise = numpy.random.normal(0, 1, (10000, 1))

        SDR, SIR, SNR = input_sxr(x, noise)

        nptest.assert_almost_equal(SDR, -3., decimal=1)
        nptest.assert_almost_equal(SIR, 0., decimal=1)
        nptest.assert_almost_equal(SNR, 0., decimal=1)


class OutputSXRTest(unittest.TestCase):

    @condition.retry(10)
    def test_for_single_input(self):
        expected_snr = numpy.array(10)
        size = (10000, 1, 1)
        x = numpy.random.normal(0, 1, size)
        noise = 10**(-expected_snr/20) * numpy.random.normal(0, 1, size)

        SDR, SIR, SNR = output_sxr(x, noise)

        nptest.assert_almost_equal(SDR, expected_snr, decimal=1)
        self.assertTrue(numpy.isinf(SIR))
        nptest.assert_almost_equal(SNR, expected_snr, decimal=1)

    @condition.retry(10)
    def test_two_equal_inputs_no_noise(self):
        expected_sir = numpy.array(20)
        size = (10000, 2, 2)
        x = numpy.random.normal(0, 1, size)
        x[:, 0, 1] = 10**(-expected_sir/20) * x[:, 0, 0]
        x[:, 1, 1] = x[:, 0, 1]
        x[:, 1, 0] = 10**(-expected_sir/20) * x[:, 0, 1]
        noise = numpy.zeros((10000, 2))

        SDR, SIR, SNR = output_sxr(x, noise)

        nptest.assert_almost_equal(SDR, 20., decimal=1)
        nptest.assert_almost_equal(SIR, 20., decimal=1)
        self.assertTrue(numpy.isinf(SNR).all())

    @condition.retry(10)
    def test_two_equal_inputs_equal_noise(self):
        size = (10000, 2, 2)
        x = numpy.random.normal(0, 1, size)
        noise = numpy.random.normal(0, 1, (10000, 2))

        SDR, SIR, SNR = output_sxr(x, noise)

        nptest.assert_almost_equal(SDR, -3., decimal=1)
        nptest.assert_almost_equal(SIR, 0, decimal=1)
        nptest.assert_almost_equal(SNR, 0, decimal=1)