"""
phase_view.py
-------------
Phase portrait widget: plots the trajectory of the system in state space.

2D mode  — e.g. predator vs prey: reveals orbital structure, fixed points,
           limit cycles, and separatrices.
3D mode  — e.g. Lorenz attractor: shows the full trajectory in R^3.

How to read a phase portrait
-----------------------------
- Each point (X, Y) is a system state, not a time value.
- The curve shows how the system moves through state space over time.
- Closed loops  -> periodic / oscillatory dynamics (Lotka-Volterra).
- Spiralling in -> stable equilibrium (damped system).
- Strange shape -> chaotic attractor (Lorenz).
"""

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
from matplotlib.figure import Figure


class PhaseView(QWidget):
    """2D / 3D phase portrait embedded in a PySide6 widget."""

    def __init__(self, variable_names: list[str], parent=None) -> None:
        super().__init__(parent)
        self._variable_names = variable_names
        self._ax = None

        self._figure = Figure(constrained_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._toolbar = NavToolbar(self._canvas, self)

        # --- Controls ---
        self._x_selector = QComboBox()
        self._y_selector = QComboBox()
        self._z_selector = QComboBox()
        self._3d_checkbox = QCheckBox("3D mode")
        self._3d_checkbox.stateChanged.connect(self._on_3d_toggled)

        self._x_selector.addItems(variable_names)
        self._y_selector.addItems(variable_names)
        self._z_selector.addItems(variable_names)

        # Sensible defaults: x=0, y=1, z=2 (if available)
        self._x_selector.setCurrentIndex(0)
        self._y_selector.setCurrentIndex(min(1, len(variable_names) - 1))
        self._z_selector.setCurrentIndex(min(2, len(variable_names) - 1))

        controls_box = QGroupBox("Axes")
        ctrl_form = QFormLayout(controls_box)
        ctrl_form.addRow("X axis:", self._x_selector)
        ctrl_form.addRow("Y axis:", self._y_selector)

        z_row = QHBoxLayout()
        z_row.addWidget(self._z_selector)
        z_row.addWidget(self._3d_checkbox)
        ctrl_form.addRow("Z axis:", z_row)

        self._z_selector.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(controls_box)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, stretch=1)

        self._init_axes_2d()

    # ------------------------------------------------------------------
    # Axis setup
    # ------------------------------------------------------------------

    def _on_3d_toggled(self, state: int) -> None:
        enabled = bool(state)
        self._z_selector.setEnabled(enabled)
        self._figure.clear()
        if enabled:
            self._ax = self._figure.add_subplot(111, projection="3d")
        else:
            self._init_axes_2d()
        self._canvas.draw_idle()

    def _init_axes_2d(self) -> None:
        self._figure.clear()
        self._ax = self._figure.add_subplot(111)
        self._ax.set_xlabel(self._variable_names[self._x_selector.currentIndex()])
        self._ax.set_ylabel(self._variable_names[self._y_selector.currentIndex()])
        self._ax.set_title("Phase portrait")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def plot(self, states: np.ndarray) -> None:
        """
        Draw the phase portrait from simulation states.

        Parameters
        ----------
        states : np.ndarray shape (n_steps, n_variables)
        """
        xi = self._x_selector.currentIndex()
        yi = self._y_selector.currentIndex()

        self._ax.clear()

        if self._3d_checkbox.isChecked():
            zi = self._z_selector.currentIndex()
            self._ax.plot(
                states[:, xi],
                states[:, yi],
                states[:, zi],
                lw=0.6,
                alpha=0.8,
                color="steelblue",
            )
            self._ax.set_xlabel(self._variable_names[xi])
            self._ax.set_ylabel(self._variable_names[yi])
            self._ax.set_zlabel(self._variable_names[zi])
            self._ax.set_title("Phase portrait (3D)")
        else:
            # Single line plot — fast regardless of number of steps
            self._ax.plot(
                states[:, xi],
                states[:, yi],
                lw=0.8,
                color="steelblue",
                alpha=0.8,
            )
            # Mark start and end points
            self._ax.scatter(
                states[0, xi], states[0, yi],
                color="green", zorder=5, s=50, label="start",
            )
            self._ax.scatter(
                states[-1, xi], states[-1, yi],
                color="red", zorder=5, s=50, label="end",
            )
            self._ax.set_xlabel(self._variable_names[xi])
            self._ax.set_ylabel(self._variable_names[yi])
            self._ax.set_title("Phase portrait (2D)")
            self._ax.legend(fontsize=8)

        self._canvas.draw_idle()

    def showEvent(self, event) -> None:
        """Force redraw when the tab becomes visible."""
        super().showEvent(event)
        self._canvas.draw()

    def clear(self) -> None:
        self._ax.clear()
        self._canvas.draw_idle()

    def set_variables(self, variable_names: list[str]) -> None:
        """Update selectors when the model changes."""
        self._variable_names = variable_names
        for selector in (self._x_selector, self._y_selector, self._z_selector):
            selector.clear()
            selector.addItems(variable_names)
        self._x_selector.setCurrentIndex(0)
        self._y_selector.setCurrentIndex(min(1, len(variable_names) - 1))
        self._z_selector.setCurrentIndex(min(2, len(variable_names) - 1))


