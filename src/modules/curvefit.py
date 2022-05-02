from math import ceil
from modules.utility import print_debug
import numpy as np
from copy import copy
import sympy
from scipy import interpolate as interp

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
import more_itertools as mit

plt.rc('mathtext', fontset='cm')


class Signal():
    """Represents a signal"""

    def __init__(self, magnitude=[], fsample=0, time=[], coef=[]) -> None:

        self.magnitude = magnitude
        self.fsample = fsample
        self.time = time

        if self.fsample == 0:
            self.time = time
            if len(time) != 0:
                self.fsample = len(self.magnitude)/time[-1]

        if len(time) == 0:
            if len(magnitude) != 0:
                print_debug("Time axis auto generated")
                self.time = np.arange(0, len(magnitude))/fsample
            else:
                self.time = []

        # if (self.magnitude != [] and self.time == []) or (self.magnitude == [] and self.time != []):
        #     raise Exception("Signal must have a time or fsampling vector")

        self.coefficients = coef

    def __len__(self):
        """Returns the length of the signal"""
        if self.magnitude != []:
            return len(self.magnitude)
        else:
            print_debug("Signal has 0 length")
            return 0

    def __getitem__(self, index):
        """Returns the signal at the given index"""
        return copy(Signal(self.magnitude[index], self.fsample, self.time[index]))

    def __add__(self, other):
        """Adds two signals"""
        if self.fsample == other.fsample:
            return Signal(self.magnitude + other.magnitude, self.fsample, self.time)
        else:
            raise Exception("Signals must have the same sampling frequency")

    def __subtract__(self, other):
        """Subtracts two signals"""
        if self.fsample == other.fsample:
            return Signal(self.magnitude - other.magnitude, self.fsample, self.time)
        else:
            raise Exception("Signals must have the same sampling frequency")

    def set_max_samples(self, max_samples):
        """Sets the maximum number of samples"""
        if len(self.magnitude) > max_samples:
            self.magnitude = self.magnitude[:max_samples]
            self.time = self.time[:max_samples]

    def __append__(self, other):
        """Appends two signals"""
        if self.fsample == other.fsample:
            return copy(Signal(self.magnitude + other.magnitude, self.fsample, self.time + other.time))
        else:
            raise Exception("Signals must have the same sampling frequency")

    def clip(self, direction, percentage):
        """Clips the signal"""
        percentage = percentage / 100
        if direction == "left":
            self.magnitude = self.magnitude[int(
                len(self.magnitude) * (1 - percentage)):]
            self.time = self.time[int(len(self.time) * (1 - percentage)):]
        elif direction == "right":
            self.magnitude = self.magnitude[:int(
                len(self.magnitude) * (1 - percentage))]
            self.time = self.time[:int(len(self.time) * (1 - percentage))]
        else:
            raise Exception("Direction must be left or right")

    def set_data(self, magnitude, time):
        """Sets the magnitdue and time of the signal"""
        self.magnitude = magnitude
        self.time = time
        if len(self.magnitude) != len(self.time):
            raise Exception("Signal must have the same length")
        if len(self.magnitude) != 0:
            self.fsample = len(self.magnitude)/time[-1]

    def set_coefficients(self, coef):
        self.coefficients = coef

    def get_coefficients(self):
        return self.coefficients


class ChunkedSignal(Signal):
    """Represents a chunked signal"""

    def __init__(self, signal, max_chunks: int = 0, overlap_percent: int = 0) -> None:
        super().__init__(signal.magnitude, signal.fsample, signal.time)

        self.chunk_array = []
        """Array of full chunk signal objects (includes overlap)"""
        self.chunk_length = 0
        self.overlap_percent = overlap_percent
        if len(signal.magnitude) > 0:
            self.update_chunk_size(max_chunks)
            # self.generate_chunks()

    def update_chunk_size(self, max_chunks):
        self.chunk_length = int(len(self.magnitude)/max_chunks)
        print_debug("Chunk length: " + str(self.chunk_length))
        print_debug("Overlap percent: " + str(self.overlap_percent))
        self.overlap_length = int(np.ceil(
            self.chunk_length * (self.overlap_percent/100)))  # TODO: FIX THIS
        self.generate_chunks()

    def merge_chunks(self):
        """Merges chunks into the main signal superclass"""

        # clear data
        self.time = []
        self.magnitude = []

        for index in range(0, len(self.chunk_array)):
            print_debug("Merging chunk " + str(index))
            # print_debug(self.chunk_array[index])
            # for each chunk

            averaged_overlap = []
            overwritten_chunk = []
            remaining_chunk = []

            # average the chunk+overlap and add to main signal
            if index == len(self.chunk_array) - 1:
                averaged_overlap = []  # last chunk cornercase
            elif index == 0:
                averaged_overlap = self.get_overlap_magnitudes(
                    index, "left")
            else:
                averaged_overlap = self.average_overlap(index)

            # overwrite the left side overlap of the next chunk
            # append the left averaged overlap to actual chunk

            remaining_chunk = self.get_chunk_without_overlap(
                index).magnitude[self.overlap_length:self.chunk_length-self.overlap_length]  # chunk starting after left overlap
            print_debug("Remaining chunk: " + str(remaining_chunk))

            overwritten_chunk = np.concatenate(
                (averaged_overlap, remaining_chunk), axis=None)

            print_debug("Overwritten Chunk: " + str(overwritten_chunk))
            # add to main signal

            appended_time = np.array(
                self.get_chunk_without_overlap(index).time)

            # fixing length difference in time and magnitude arrays
            if len(appended_time) != len(overwritten_chunk):
                difference = len(overwritten_chunk)-len(appended_time)
                print_debug("Target Length: " + str(len(appended_time)))
                print_debug("Length before padding: " +
                            str(len(overwritten_chunk)))
                appended_time.resize(len(overwritten_chunk))
                print_debug("Length after padding: " +
                            str(len(overwritten_chunk)))

            self.time.append(appended_time)
            self.magnitude.append(overwritten_chunk)

        # Convert to 1D arrays
        self.time = np.concatenate(self.time)
        self.magnitude = np.concatenate(self.magnitude)
        print_debug("magnitude length: " + str(len(self.magnitude)))

    def average_overlap(self, chunk_index):
        """Averages the overlap magnitude of two chunks"""
        # get the overlap of left chunk and right chunk
        right_chunk_overlap = self.get_overlap_magnitudes(
            chunk_index, "left")
        left_chunk_overlap = self.get_overlap_magnitudes(
            chunk_index-1, "right")

        print_debug("Right chunk overlap: " + str(right_chunk_overlap))
        print_debug("Left chunk overlap: " + str(left_chunk_overlap))

        # average the overlap
        average_overlap = np.mean(
            [left_chunk_overlap, right_chunk_overlap], axis=0)

        print_debug("Average overlap: " + str(average_overlap))
        # return the averaged overlap (make sure to put it in the right chunk)
        return average_overlap

    def get_overlap_magnitudes(self, chunk_index, direction="right"):
        """Returns the overlap of the chunk from the given
        \n chunk index = index of chunk to get overlap from
        \n direction = location of overlap wrt to current chunk
        \n (accounts for leftmost and rightmost cornercases)
        \n returns a magnitude array """
        overlap_length = self.overlap_length
        print_debug("Overlap length: " + str(overlap_length))
        chunk_length = self.chunk_length
        print_debug("Chunk length: " + str(chunk_length))

        if direction == "left":
            print_debug("Getting left overlap")
            chunk = self.chunk_array[chunk_index][:overlap_length].magnitude
            return chunk
        elif direction == "right":
            if chunk_index != len(self.chunk_array)-1:
                print_debug("Getting right overlap")
                return self.chunk_array[chunk_index][chunk_length-overlap_length:].magnitude
            else:
                if overlap_length != 0:
                    overlap_length -= 1
                return np.zeros(overlap_length)  # Zero padding
        else:
            raise Exception("Direction must be left or right")

    def get_chunk(self, index):
        """Returns the chunk at the given index"""
        return self.chunk_array[index]

    #TODO: rename
    def get_chunk_without_overlap(self, index):
        """Returns the chunk signal object without overlap"""
        output = copy(self.chunk_array[index][:self.chunk_length])
        print_debug(" Chunk without overlap" + str(output))
        return output

    def get_coefficients(self, index=0):
        """Returns the coefficients of the chunk at the given index"""
        return self.chunk_array[index].coefficients

    def set_chunk(self, chunk_index, signal):
        """Modifies a single chunk signal"""
        # TODO: add corner case
        # add signal object to chunk
        self.chunk_array[chunk_index] = signal
        # call update merged chunks
        self.merge_chunks()

    def generate_chunks(self):
        """Generates signal objects for each chunk + overlap"""

        # generate chunks
        chunk_array = []
        chunk_length = self.chunk_length
        overlap_length = self.overlap_length

        magnitude_chunks = list(mit.windowed(
            seq=self.magnitude, n=chunk_length, step=(chunk_length-overlap_length), fillvalue=0))
        time_chunks = list(mit.windowed(
            seq=self.time, n=chunk_length, step=(chunk_length-overlap_length), fillvalue=0))

        for index in range(len(magnitude_chunks)):
            print_debug("Chunk " + str(index) + ": " +
                        str(magnitude_chunks[index]))
            print_debug("Time " + str(index) + ": " + str(time_chunks[index]))
            chunk_array.append(Signal(magnitude=list(magnitude_chunks[index]),
                                      fsample=self.fsample,
                                      time=list(time_chunks[index]),
                                      coef=self.coefficients))

        self.chunk_array = chunk_array


class SignalProcessor():
    def __init__(self, original=Signal()) -> None:

        self.original_signal = copy(original)

        self.clipped_signal = copy(original)
        self.clip_percentage = 100

        self.interpolation_type = None
        self.interpolation_order = 0
        self.max_chunks = 1
        self.overlap_percent = 0
        self.smoothing_factor = 0

        self.extrapolation_type = None

        self.interpolated_signal = copy(original)
        self.extrapolated_signal = copy(original)

    def init_interpolation(self, type: str = None, order: int = 1, N_chunks: int = 1, overlap_percent: int = 0, smoothing_factor=0):
        if type == None:
            raise Exception("Interpolation type must be set")
        # TODO: Rethink updating to reduce code repetition
        if type == "polynomial":
            self.interpolation_type = type
            self.interpolation_order = order
            if len(self.original_signal) != 0:
                self.max_chunks = N_chunks
                if N_chunks > 1:
                    self.overlap_percent = overlap_percent
                    self.update_chunks(N_chunks, overlap_percent)
        elif type == "spline":

            self.interpolation_type = type
            self.interpolation_order = order
            self.smoothing_factor = 10 - (smoothing_factor/10)
        self.interpolate()

    def interpolate(self):
        type = self.interpolation_type
        input = self.clipped_signal

        if type == "spline":
            self.interpolated_signal = copy(self.clipped_signal)

            input = self.clipped_signal

            spl = interp.UnivariateSpline(input.time,
                                          input.magnitude,
                                          k=self.interpolation_order,
                                          s=self.smoothing_factor)

            self.interpolated_signal.magnitude = spl(input.time)

        elif type == "polynomial":
            self.clipped_signal = ChunkedSignal(
                self.clipped_signal, self.max_chunks, self.overlap_percent)
            self.interpolated_signal = copy(self.clipped_signal)

            for chunk_index in range(len(self.clipped_signal.chunk_array)):
                input = self.clipped_signal.get_chunk(chunk_index)
                coef = np.polyfit(input.time,
                                  input.magnitude,
                                  self.interpolation_order)
                self.interpolated_signal.set_chunk(chunk_index, Signal(
                    magnitude=np.polyval(coef, input.time), fsample=input.fsample, coef=coef, time=input.time))
        else:
            raise Exception("Interpolation type must be polynomial or spline")

    def extrapolate(self):
        """Extrapolates remaining signal, starting from N of clipped to N of original"""
        self.extrapolation_type = self.interpolation_type  # placeholder for now

        N_clipped = len(self.clipped_signal)
        N_original = len(self.original_signal)

        """Processing Here"""
        # fitting the clipped signal
        if self.extrapolation_type == "spline":
            spl = interp.UnivariateSpline(self.clipped_signal.time,
                                          self.clipped_signal.magnitude,
                                          k=self.interpolation_order,
                                          s=self.smoothing_factor,
                                          ext=0)

            # plot remaining time
            self.extrapolated_values = spl(
                self.original_signal.time[N_clipped:N_original])

        elif self.extrapolation_type == "polynomial":
            # coefficients of last chunk
            coef = self.interpolated_signal.chunk_array[-1].coefficients
            self.extrapolated_values = np.polyval(
                coef, self.original_signal.time[N_clipped:N_original])
            pass

        """Output signal here"""
        self.extrapolated_signal = Signal(
            magnitude=self.extrapolated_values, time=self.original_signal.time[N_clipped:N_original])

    def set_clipping(self, clip_percentage: int = 0):
        if clip_percentage == 100:
            raise Exception("Clip percentage cant be 100%")

        self.clip_percentage = clip_percentage
        # Resets the clipped signal
        self.clipped_signal = copy(self.original_signal)
        self.clipped_signal.clip("right", self.clip_percentage)

    def update_chunks(self, max_chunks: int, overlap_percent: int = 0):
        """Converts clipped signal object to chunked signal object"""
        self.max_chunks = max_chunks
        self.clipped_signal = ChunkedSignal(
            self.clipped_signal, max_chunks, overlap_percent)

    def isInterpolated(self):
        if self.interpolation_type == None:
            return False
        else:
            return True

    def isExtrapolated(self):
        if self.extrapolation_type == None:
            return False
        else:
            return True

    def percentage_error(self):
        interpolated = self.interpolated_signal.magnitude
        original = self.original_signal.magnitude[0:len(interpolated)]

        self.sub = np.subtract(original, interpolated)

        original_minus_interpolated = np.average(np.absolute(self.sub))
        original_avg = np.average(original)

        self.percentageoferror = np.absolute(
            original_minus_interpolated / original_avg)*100
        return self.percentageoferror


def update_graph(self):
    if self.signal_processor.original_signal != None:
        draw = self.signal_processor.original_signal
        self.curve_plot_ref.setData(draw.time, draw.magnitude)

    if self.signal_processor.isInterpolated():
        draw = self.signal_processor.interpolated_signal
        self.curve_plot_interpolated.setData(draw.time, draw.magnitude)

        if self.signal_processor.interpolation_type == "polynomial":
            draw = self.signal_processor.interpolated_signal.chunk_array[self.polynomial_equation_spinBox.value(
            )]
            self.curve_plot_selected_chunk.setData(draw.time, draw.magnitude)
        else:
            self.curve_plot_selected_chunk.setData([], [])

    if self.signal_processor.isExtrapolated():
        draw = self.signal_processor.extrapolated_signal
        self.curve_plot_extrapolated.setData(draw.time, draw.magnitude)

    update_latex(self)


def update_latex(self):
    if self.signal_processor.interpolation_type == "polynomial":
        latex(self, self.signal_processor.interpolated_signal.get_coefficients(
            self.polynomial_equation_spinBox.value()))
        self.polynomial_equation_spinBox.setMaximum(
            self.chunk_number_spinBox.value() - 1)
        draw = self.signal_processor.interpolated_signal.chunk_array[self.polynomial_equation_spinBox.value(
        )]
        self.curve_plot_selected_chunk.setData(draw.time, draw.magnitude)

    else:
        latex(self, self.signal_processor.interpolated_signal.coefficients)


def create_latex_figure(self):
    self.fig = plt.figure()
    self.fig.patch.set_facecolor('None')
    self.Latex = Canvas(self.fig)
    self.latex_box.addWidget(self.Latex)


def latex(self, coef, fontsize=12):
    self.fig.clear()
    polynomial = np.poly1d(coef)
    x = sympy.symbols('x')
    formula = sympy.printing.latex(sympy.Poly(
        polynomial.coef.round(2), x).as_expr())
    self.fig.text(0, 0.1, '${}$'.format(formula),
                  fontsize=fontsize, color='white')
    self.fig.canvas.draw()
