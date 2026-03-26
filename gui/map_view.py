"""
map_view.py
-----------
PySide6 widget that shows the 2D spatial grid as a heatmap.
Uses matplotlib's imshow; updates in place for performance.
"""

import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QLabel, QHBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.colorbar


class MapView(QWidget):
    """Heatmap display for a single variable of the spatial Grid."""

    def __init__(self, variable_names: list[str], parent=None) -> None:
        super().__init__(parent)

        self._variable_names = variable_names
        self._image = None
        self._colorbar = None

        # Matplotlib figure
        self._figure = Figure(figsize=(5, 5), tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        # Variable selector
        self._selector = QComboBox()
        self._selector.addItems(variable_names)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Show variable:"))
        top_bar.addWidget(self._selector)
        top_bar.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top_bar)
        layout.addWidget(self._canvas)

    @property
    def selected_variable(self) -> int:
        return self._selector.currentIndex()

    def render(self, grid_state: np.ndarray) -> None:
        """
        Update the heatmap.

        Parameters
        ----------
        grid_state : np.ndarray shape (n_variables, height, width)
        """
        v = self.selected_variable
        data = grid_state[v]

        if self._image is None:
            self._ax.clear()
            self._image = self._ax.imshow(
                data,
                origin="lower",
                cmap="viridis",
                interpolation="nearest",
                vmin=0,
            )
            self._colorbar = self._figure.colorbar(self._image, ax=self._ax)
            self._ax.set_title(self._variable_names[v])
        else:
            self._image.set_data(data)
            self._image.set_clim(vmin=0, vmax=max(data.max(), 1e-6))
            self._ax.set_title(self._variable_names[v])

        self._canvas.draw()

    def reset(self) -> None:
        """Clear and reset so the next render() rebuilds the image."""
        self._image = None
        if self._colorbar is not None:
            self._colorbar.remove()
            self._colorbar = None
        self._ax.clear()
        self._canvas.draw()
