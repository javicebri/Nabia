"""
main_window.py
--------------
Main application window for Nabia.

Layout
------
  Left panel  : model selector, parameter form, solver controls,
                stop conditions, CSV loader
  Center tabs :
    [0] Population over time  — X(t), Y(t) time series
    [1] Phase portrait        — trajectory in state space (2D / 3D)
    [2] Spatial — 2D Map      — reaction-diffusion heatmap
"""

import csv
import importlib
import importlib.util
import os
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.map_view import MapView
from gui.phase_view import PhaseView
from gui.plot_view import PlotView
from simulation.grid import Grid
from simulation.solver import SOLVERS

MODELS_DIR = Path(__file__).parent.parent / "models"


def _load_model(name: str):
    """Import a model module by filename (without .py)."""
    spec_path = MODELS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, spec_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _available_models() -> list[str]:
    return [
        p.stem
        for p in sorted(MODELS_DIR.glob("*.py"))
        if p.stem not in ("__init__", "base_model")
    ]


class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nabia — Ecosystem Simulator")
        self.resize(1280, 760)

        self._model = None
        self._params: dict = {}
        self._param_widgets: dict = {}
        self._last_times: np.ndarray | None = None
        self._last_states: np.ndarray | None = None

        # Step-by-step state
        self._step_t: float = 0.0
        self._step_state: list[float] = []
        self._step_times: list[float] = []
        self._step_states: list[list[float]] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._spatial_step)
        self._spatial_grid: Grid | None = None
        self._spatial_step_count = 0

        self._build_ui()
        self._populate_model_selector()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(self._build_left_panel(), stretch=0)
        root.addWidget(self._build_center_panel(), stretch=1)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready.")

    def _build_left_panel(self) -> QWidget:
        # Wrap in a scroll area so the panel survives many parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(300)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Model selector
        model_box = QGroupBox("Model")
        model_layout = QVBoxLayout(model_box)
        self._model_selector = QComboBox()
        self._model_selector.currentTextChanged.connect(self._on_model_changed)
        model_layout.addWidget(self._model_selector)
        layout.addWidget(model_box)

        # Parameters
        params_box = QGroupBox("Parameters")
        self._params_form = QFormLayout()
        self._params_form.setContentsMargins(4, 4, 4, 4)
        params_box.setLayout(self._params_form)
        layout.addWidget(params_box)

        # CSV loader
        csv_box = QGroupBox("Species / Initial conditions (CSV)")
        csv_layout = QVBoxLayout(csv_box)
        self._csv_label = QLabel("No file loaded.")
        self._csv_label.setWordWrap(True)
        load_csv_btn = QPushButton("Load CSV…")
        load_csv_btn.clicked.connect(self._load_csv)
        csv_layout.addWidget(self._csv_label)
        csv_layout.addWidget(load_csv_btn)
        layout.addWidget(csv_box)

        # ODE controls
        ode_box = QGroupBox("ODE simulation")
        ode_layout = QFormLayout(ode_box)

        self._solver_selector = QComboBox()
        self._solver_selector.addItems(list(SOLVERS.keys()))
        self._solver_selector.setCurrentText("RK4")
        ode_layout.addRow("Solver:", self._solver_selector)

        self._t_end_spin = QDoubleSpinBox()
        self._t_end_spin.setRange(1, 10_000)
        self._t_end_spin.setValue(50.0)
        self._t_end_spin.setSingleStep(10)
        ode_layout.addRow("Duration (t):", self._t_end_spin)

        self._dt_spin = QDoubleSpinBox()
        self._dt_spin.setRange(0.0001, 1.0)
        self._dt_spin.setValue(0.05)
        self._dt_spin.setDecimals(4)
        ode_layout.addRow("Time step dt:", self._dt_spin)

        run_ode_btn = QPushButton("Run ODE")
        run_ode_btn.clicked.connect(self._run_ode)
        ode_layout.addRow(run_ode_btn)

        step_row = QHBoxLayout()
        self._step_btn = QPushButton("Step ▶")
        self._step_btn.setToolTip("Advance one dt step and update the plots")
        self._step_btn.clicked.connect(self._do_step)
        reset_step_btn = QPushButton("Reset ↺")
        reset_step_btn.setToolTip("Reset to initial conditions")
        reset_step_btn.clicked.connect(self._reset_step)
        step_row.addWidget(self._step_btn)
        step_row.addWidget(reset_step_btn)
        ode_layout.addRow(step_row)

        self._step_label = QLabel("t = 0.00   step = 0")
        self._step_label.setStyleSheet("color: gray; font-size: 11px;")
        ode_layout.addRow(self._step_label)

        layout.addWidget(ode_box)

        # Stop conditions
        stop_box = QGroupBox("Stop conditions")
        stop_layout = QFormLayout(stop_box)

        self._stop_equilibrium_cb = QCheckBox("At equilibrium")
        self._stop_equilibrium_cb.setToolTip(
            "Stop when all |derivatives| < threshold"
        )
        self._equilibrium_thr_spin = QDoubleSpinBox()
        self._equilibrium_thr_spin.setRange(1e-8, 1.0)
        self._equilibrium_thr_spin.setValue(1e-4)
        self._equilibrium_thr_spin.setDecimals(8)
        eq_row = QHBoxLayout()
        eq_row.addWidget(self._stop_equilibrium_cb)
        eq_row.addWidget(QLabel("thr:"))
        eq_row.addWidget(self._equilibrium_thr_spin)
        stop_layout.addRow(eq_row)

        self._stop_var_cb = QCheckBox("When variable")
        self._stop_var_selector = QComboBox()
        self._stop_var_condition = QComboBox()
        self._stop_var_condition.addItems([">", "<", "="])
        self._stop_var_value = QDoubleSpinBox()
        self._stop_var_value.setRange(-1e6, 1e6)
        self._stop_var_value.setValue(0.1)
        var_row = QHBoxLayout()
        var_row.addWidget(self._stop_var_cb)
        var_row.addWidget(self._stop_var_selector)
        var_row.addWidget(self._stop_var_condition)
        var_row.addWidget(self._stop_var_value)
        stop_layout.addRow(var_row)

        layout.addWidget(stop_box)

        # Spatial controls
        spatial_box = QGroupBox("Spatial simulation")
        spatial_layout = QFormLayout(spatial_box)

        self._grid_size_spin = QSpinBox()
        self._grid_size_spin.setRange(10, 500)
        self._grid_size_spin.setValue(100)
        spatial_layout.addRow("Grid size:", self._grid_size_spin)

        self._spatial_dt_spin = QDoubleSpinBox()
        self._spatial_dt_spin.setRange(0.001, 1.0)
        self._spatial_dt_spin.setValue(0.05)
        self._spatial_dt_spin.setDecimals(3)
        spatial_layout.addRow("dt:", self._spatial_dt_spin)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 60)
        self._fps_spin.setValue(20)
        spatial_layout.addRow("FPS:", self._fps_spin)

        btn_row = QHBoxLayout()
        self._start_spatial_btn = QPushButton("Start")
        self._stop_spatial_btn = QPushButton("Stop")
        self._stop_spatial_btn.setEnabled(False)
        self._start_spatial_btn.clicked.connect(self._start_spatial)
        self._stop_spatial_btn.clicked.connect(self._stop_spatial)
        btn_row.addWidget(self._start_spatial_btn)
        btn_row.addWidget(self._stop_spatial_btn)
        spatial_layout.addRow(btn_row)
        layout.addWidget(spatial_box)

        layout.addStretch()
        scroll.setWidget(panel)
        return scroll

    def _build_center_panel(self) -> QWidget:
        self._tabs = QTabWidget()

        self._plot_view = PlotView()
        self._tabs.addTab(self._plot_view, "Population over time")

        # Phase portrait — placeholder until model loads
        self._phase_view = PhaseView(["x", "y"])
        self._tabs.addTab(self._phase_view, "Phase portrait")

        self._map_placeholder = QLabel("Load a model to enable spatial view.")
        self._map_placeholder.setStyleSheet("color: gray; padding: 16px;")
        self._tabs.addTab(self._map_placeholder, "Spatial — 2D Map")

        return self._tabs

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _populate_model_selector(self) -> None:
        models = _available_models()
        self._model_selector.addItems(models)
        if models:
            self._on_model_changed(models[0])

    def _on_model_changed(self, name: str) -> None:
        if not name:
            return
        try:
            self._model = _load_model(name)
        except Exception as exc:
            QMessageBox.critical(self, "Model error", str(exc))
            return

        self._params = dict(self._model.DEFAULT_PARAMS)
        self._rebuild_params_form()
        self._rebuild_phase_tab()
        self._rebuild_map_tab()
        self._plot_view.clear()
        self._phase_view.clear()
        self._last_times = None
        self._last_states = None
        self._step_t = 0.0
        self._step_state = []
        self._step_times = []
        self._step_states = []
        self._step_label.setText("t = 0.00   step = 0")
        self._status.showMessage(f"Model loaded: {self._model.NAME}")

    def _rebuild_params_form(self) -> None:
        while self._params_form.rowCount():
            self._params_form.removeRow(0)
        self._param_widgets.clear()

        for key, value in self._params.items():
            spin = QDoubleSpinBox()
            spin.setRange(-1e6, 1e6)
            spin.setDecimals(4)
            spin.setSingleStep(0.01)
            spin.setValue(float(value))
            spin.valueChanged.connect(lambda val, k=key: self._params.update({k: val}))
            self._param_widgets[key] = spin
            self._params_form.addRow(key + ":", spin)

        # Update stop-condition variable selector
        self._stop_var_selector.clear()
        self._stop_var_selector.addItems(self._model.VARIABLES)

    def _rebuild_phase_tab(self) -> None:
        if self._model is None:
            return
        self._phase_view.set_variables(self._model.VARIABLES)

    def _rebuild_map_tab(self) -> None:
        if self._model is None:
            return
        self._map_view = MapView(self._model.VARIABLES)
        self._tabs.removeTab(2)
        self._tabs.insertTab(2, self._map_view, "Spatial — 2D Map")

    # ------------------------------------------------------------------
    # CSV loading
    # ------------------------------------------------------------------

    def _load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open species CSV",
            str(Path(__file__).parent.parent / "data" / "species"),
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as exc:
            QMessageBox.critical(self, "CSV error", str(exc))
            return

        if not rows:
            self._csv_label.setText("CSV is empty.")
            return

        row = rows[0]
        updated = []
        for key in self._params:
            if key in row:
                val = float(row[key])
                self._params[key] = val
                if key in self._param_widgets:
                    self._param_widgets[key].setValue(val)
                updated.append(key)

        self._csv_label.setText(
            f"{os.path.basename(path)}\n"
            f"({len(rows)} rows, updated: {', '.join(updated) or 'none'})"
        )
        self._status.showMessage(f"CSV loaded: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Stop condition builder
    # ------------------------------------------------------------------

    def _build_stop_condition(self):
        """Return a stop_condition callable, or None if no condition is active."""
        conditions = []

        if self._stop_equilibrium_cb.isChecked():
            thr = self._equilibrium_thr_spin.value()
            model = self._model
            params = self._params

            def _equilibrium(state, t):
                derivs = model.derivatives(state, t, params)
                return all(abs(d) < thr for d in derivs)

            conditions.append(_equilibrium)

        if self._stop_var_cb.isChecked():
            var_idx = self._stop_var_selector.currentIndex()
            op = self._stop_var_condition.currentText()
            target = self._stop_var_value.value()

            def _var_threshold(state, t, _idx=var_idx, _op=op, _tgt=target):
                val = state[_idx]
                if _op == ">":
                    return val > _tgt
                if _op == "<":
                    return val < _tgt
                return abs(val - _tgt) < 1e-6

            conditions.append(_var_threshold)

        if not conditions:
            return None

        def _combined(state, t):
            return any(fn(state, t) for fn in conditions)

        return _combined

    # ------------------------------------------------------------------
    # ODE simulation
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Step-by-step simulation
    # ------------------------------------------------------------------

    def _reset_step(self) -> None:
        """Reset step state to initial conditions and clear plots."""
        if self._model is None:
            return
        self._step_t = 0.0
        self._step_state = list(self._model.DEFAULT_INITIAL_STATE)
        self._step_times = [0.0]
        self._step_states = [list(self._model.DEFAULT_INITIAL_STATE)]
        self._step_label.setText("t = 0.00   step = 0")
        self._plot_view.clear()
        self._phase_view.clear()
        self._status.showMessage("Step reset to initial conditions.")

    def _do_step(self) -> None:
        """Advance the simulation by one dt step."""
        if self._model is None:
            return

        # Initialise on first step if never reset
        if not self._step_state:
            self._reset_step()

        dt = self._dt_spin.value()
        solver_fn = SOLVERS[self._solver_selector.currentText()]

        # Run solver for exactly one step: t_span covers [t, t+dt]
        _, result = solver_fn(
            self._model.derivatives,
            self._step_state,
            (self._step_t, self._step_t + dt),
            dt,
            self._params,
        )
        # result has shape (2, n_vars): row 0 = current, row 1 = next
        self._step_t += dt
        self._step_state = result[-1].tolist()
        self._step_times.append(self._step_t)
        self._step_states.append(self._step_state)

        times = np.array(self._step_times)
        states = np.array(self._step_states)
        self._plot_view.plot(times, states, self._model.VARIABLES)
        self._phase_view.plot(states)

        n = len(self._step_times) - 1
        self._step_label.setText(f"t = {self._step_t:.4f}   step = {n}")
        self._status.showMessage(
            f"Step {n} — t = {self._step_t:.4f} — "
            f"state = [{', '.join(f'{v:.3f}' for v in self._step_state)}]"
        )

    def _run_ode(self) -> None:
        if self._model is None:
            return

        initial_state = list(self._model.DEFAULT_INITIAL_STATE)
        solver_fn = SOLVERS[self._solver_selector.currentText()]
        t_span = (0.0, self._t_end_spin.value())
        dt = self._dt_spin.value()
        stop_condition = self._build_stop_condition()

        try:
            times, states = solver_fn(
                self._model.derivatives,
                initial_state,
                t_span,
                dt,
                self._params,
                stop_condition,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Solver error", str(exc))
            return

        self._last_times = times
        self._last_states = states

        self._plot_view.plot(times, states, self._model.VARIABLES)
        self._phase_view.plot(states)

        stop_note = f" (stopped early at t={times[-1]:.2f})" if len(times) < int((t_span[1] - t_span[0]) / dt) else ""
        self._status.showMessage(
            f"ODE done — {len(times)} steps, solver: {self._solver_selector.currentText()}{stop_note}"
        )

    # ------------------------------------------------------------------
    # Spatial simulation
    # ------------------------------------------------------------------

    def _start_spatial(self) -> None:
        if self._model is None:
            return

        size = self._grid_size_spin.value()
        n_vars = len(self._model.VARIABLES)
        self._spatial_grid = Grid(size, size, n_vars)
        self._spatial_grid.randomize(
            means=list(self._model.DEFAULT_INITIAL_STATE),
            noise=2.0,
        )
        self._map_view.reset()
        self._spatial_step_count = 0

        interval_ms = max(1, int(1000 / self._fps_spin.value()))
        self._timer.start(interval_ms)

        self._start_spatial_btn.setEnabled(False)
        self._stop_spatial_btn.setEnabled(True)
        self._tabs.setCurrentIndex(2)
        self._status.showMessage("Spatial simulation running…")

    def _stop_spatial(self) -> None:
        self._timer.stop()
        self._start_spatial_btn.setEnabled(True)
        self._stop_spatial_btn.setEnabled(False)
        self._status.showMessage(f"Stopped at step {self._spatial_step_count}.")

    def _spatial_step(self) -> None:
        if self._spatial_grid is None or self._model is None:
            return

        dt = self._spatial_dt_spin.value()
        diffusion = [
            self._params.get("D_prey", 0.1),
            self._params.get("D_predator", 0.05),
        ]

        self._spatial_grid.step(self._model.derivatives, self._params, dt, diffusion)
        self._spatial_step_count += 1
        self._map_view.render(self._spatial_grid.state)
        self._status.showMessage(f"Spatial step: {self._spatial_step_count}")
