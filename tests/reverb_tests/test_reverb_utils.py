import numpy
import unittest
from nt.utils.matlab import Mlab, matlab_test
import nt.testing as tc
import numpy.testing as nptest
import nt.reverb.reverb_utils as rirUtils

# Uncomment, if you want to test Matlab functions.
matlab_test = unittest.skipUnless(True, 'matlab-test')

class TestReverbUtils(unittest.TestCase):

    @classmethod
    def setUpClass(self):

        self.matlab_session = Mlab()
        self.sample_rate = 16000  # Hz
        self.filter_length = 2**13
        self.room_dimensions = (10, 10, 4)  # meter

    @matlab_test
    def test_comparePythonTranVuRirWithExpectedUsingMatlabTwoSensorTwoSrc(self):
        """
        Compare RIR calculated by Matlabs reverb.generate(..) "Tranvu"
        algorithm with RIR calculated by Python reverb_utils.generate_RIR(..)
        "Tranvu" algorithm.
        Here: 2 randomly placed sensors and sources each
        """
        number_of_sources = 2
        number_of_sensors = 2
        reverberation_time = 0.1

        sources, mics = rirUtils.generateRandomSourcesAndSensors(
            self.room_dimensions,
            number_of_sources,
            number_of_sensors
        )

        matlab_session = self.matlab_session
        pyRIR = rirUtils.generate_RIR(
            self.room_dimensions,
            sources,
            mics,
            self.sample_rate,
            self.filter_length,
            reverberation_time
        )

        matlab_session.run_code("roomDim = [{0}; {1}; {2}]".format(self.room_dimensions[0],
                                                         self.room_dimensions[1],
                                                         self.room_dimensions[2]))
        matlab_session.run_code("src = zeros(3,1); sensors = zeros(3,1);")
        for s in range(number_of_sources):
            matlab_session.run_code("srctemp = [{0};{1};{2}]".format(sources[s][0],
                                                           sources[s][1],
                                                           sources[s][2]))
            matlab_session.run_code("src = [src srctemp]")
        for m in range(number_of_sensors):
            matlab_session.run_code("sensorstemp = [{0};{1};{2}]".format(mics[m][0],
                                                               mics[m][1],
                                                               mics[m][2]))
            matlab_session.run_code("sensors = [sensors sensorstemp]")

        matlab_session.run_code("src = src(:,2:end)")
        matlab_session.run_code("sensors = sensors(:,2:end)")

        matlab_session.run_code("sampleRate = {0}".format(self.sample_rate))
        matlab_session.run_code("filterLength = {0}".format(self.filter_length))
        matlab_session.run_code("T60 = {0}".format(reverberation_time))

        matlab_session.run_code("rir = reverb.generate(roomDim, src, sensors, sampleRate, "+
                     "filterLength, T60, 'algorithm', 'TranVu');")

        matlabRIR = matlab_session.get_variable('rir')
        tc.assert_allclose(matlabRIR, pyRIR, atol=1e-4)

    def test_compareTranVuMinimumTimeDelayWithSoundVelocity(self):
        """
        Compare theoretical TimeDelay from distance and soundvelocity with
        timedelay found via index of maximum value in calculated RIR.
        Here: 1 Source, 1 Sensor, no reflections, that is, T60 = 0
        """
        numSrcs = 1
        numMics = 1
        T60 = 0

        sources, mics = rirUtils.generateRandomSourcesAndSensors(
            self.room_dimensions,
            numSrcs,
            numMics
        )
        distance = numpy.linalg.norm(numpy.asarray(sources)-numpy.asarray(mics))

        # Tranvu: first index of returned RIR equals time-index minus 128
        fixedshift = 128
        RIR = rirUtils.generate_RIR(
            self.room_dimensions,
            sources,
            mics,
            self.sample_rate,
            self.filter_length,
            T60
        )
        peak = numpy.argmax(RIR) - fixedshift
        actual = peak / self.sample_rate
        expected = distance / 343
        tc.assert_allclose(actual, expected, atol=1e-4)

    @unittest.skip("")
    @matlab_test
    def test_compareTranVuExpectedT60WithCalculatedUsingSchroederMethod(self):
        pass

    @unittest.skip("")
    @matlab_test
    def test_compareDirectivityWithExpectedUsingTranVu(self):
        pass

    @unittest.skip("")
    @matlab_test
    def test_compareAzimuthSensorOrientationWithExpectedUsingTranVu(self):
        pass

    @unittest.skip("")
    @matlab_test
    def test_compareElevationSensorOrientationWithExpectedUsingTranvu(self):
        pass

    @unittest.skip("")
    @matlab_test
    def test_compareTranVuExpectedT60WithCalculatedUsingSchroederMethod(self):
        pass