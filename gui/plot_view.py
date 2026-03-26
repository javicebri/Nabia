"""
plot_view.py
------------
PySide6 widget that embeds a matplotlib figure for time-series plots.
Shows population densities over time for each model variable.
"""

import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
from matplotlib.figure import Figure


class PlotView(QWidget):
    """Time-series plot for ODE simulation results."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._figure = Figure(constrained_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._toolbar = NavToolbar(self._canvas, self)
        self._ax = self._figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)

    def plot(
        self,
        times: np.ndarray,
        states: np.ndarray,
        variable_names: list[str],
    ) -> None:
        self._ax.clear()
        for i, name in enumerate(variable_names):
            self._ax.plot(times, states[:, i], label=name)
        self._ax.set_xlabel("Time")
        self._ax.set_ylabel("Population density")
        self._ax.set_title("Population over time")
        self._ax.legend()
        self._canvas.draw_idle()

    def showEvent(self, event) -> None:
        """Force redraw when the tab becomes visible."""
        super().showEvent(event)
        self._canvas.draw()

    def clear(self) -> None:
        self._ax.clear()
        self._canvas.draw_idle()
