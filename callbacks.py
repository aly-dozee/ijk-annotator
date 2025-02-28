import dash
from dash import Input, Output, State, ctx, dcc
from datetime import datetime, timedelta
import json
import io
import pandas as pd
import numpy as np
from parse_data import sos_filter
import plotly.graph_objects as go
import os
import warnings

warnings.simplefilter("ignore", category=UserWarning)

from datetime import timedelta

def index_to_timestamp(start_ts, sample_rate, index):
    """Convert an index to a timestamp string"""
    start_dt = datetime.fromtimestamp(start_ts)
    offset_seconds = float(index) / sample_rate
    timestamp = start_dt + timedelta(seconds=offset_seconds)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Format with milliseconds

def register_callbacks(app, signals_data, duration):
    """
    Final callbacks:
     - One column for j_conf
     - Combined X info in x_j: "index (timestamp)"
     - Only add row on confidence -> no double-add
    """

    #
    # 1) Toggle the dropdown container's visibility
    #
    @app.callback(
        Output("signal-dropdown-container", "style"),
        Input("toggle-dropdown-btn", "n_clicks"),
        State("signal-dropdown-container", "style"),
        prevent_initial_call=True
    )
    def toggle_dropdown(n, current_style):
        if not current_style:
            current_style = {}
        return {
            **current_style,
            "display": "block" if current_style.get("display", "none") == "none" else "none"
        }

    #
    # 2) Main Plot Update
    #
    @app.callback(
        Output("main-plot", "figure"),
        [
            Input("signal-dropdown", "value"),
            Input("table-store", "data"),
            Input("annotation-store", "data"),
            # Filter controls
            Input("filter-order-input", "value"),
            Input("lowcut-input", "value"),
            Input("highcut-input", "value"),
        ]
    )
    def update_plot(selected_value, table_data, annot_state,
                    filter_order, lowcut, highcut):
        fig = go.Figure()

        if selected_value is None or selected_value not in range(len(signals_data)):
            fig.update_layout(title="No Signal Selected", uirevision="signalPlot")
            return fig

        entry = signals_data[selected_value]
        ts = entry["ts"]
        signal_values = entry["signals"]
        ecg = entry.get("ecg", None)
        mask_arr = entry.get("mask", None)
        num_samples = len(signal_values)

        # X-axis times
        start_dt = datetime.fromtimestamp(ts)
        step_sec = duration / (num_samples - 1) if num_samples > 1 else 1
        x_axis = [start_dt + timedelta(seconds=i * step_sec) for i in range(num_samples)]

        # If mask: vertical lines
        if mask_arr is not None and len(mask_arr) == num_samples:
            y_min, y_max = min(signal_values), max(signal_values)
            x_mask, y_mask = [], []
            for i, val in enumerate(mask_arr):
                if val == 1:
                    x_mask.extend([x_axis[i], x_axis[i], None])
                    y_mask.extend([y_min, y_max, None])
            if any(pt is not None for pt in x_mask):
                fig.add_trace(go.Scatter(
                    x=x_mask,
                    y=y_mask,
                    mode="lines",
                    name="Mask",
                    line=dict(color="blue", width=2),
                    opacity=0.7,
                    hoverinfo="skip",
                    showlegend=True
                ))

        # Raw signal
        fig.add_trace(go.Scatter(
            x=x_axis,
            y=signal_values,
            mode="lines",
            name="Raw Signal",
            line=dict(color="black", width=2.5),
            hoverinfo="x+y"
        ))

        # Filter controls
        if not filter_order:
            filter_order = 2
        if not lowcut:
            lowcut = 5.0
        if not highcut:
            highcut = 15.0

        filtered_signal = sos_filter(
            signal_values,
            order=filter_order,
            frequency_list=[lowcut, highcut],
            sample_rate=250
        )
        fig.add_trace(go.Scatter(
            x=x_axis,
            y=filtered_signal + np.mean(signal_values),
            mode="lines",
            name="Filtered",
            line=dict(color="firebrick", width=2),
            opacity=0.8,
            hoverinfo="skip",
            showlegend=True
        ))

        # If we store final j-peaks in the table as rows with x_j (string), j_amp, j_conf
        # we can parse them if needed, but simpler to just show the amplitude as is
        # The user sees the markers in the table
        if table_data and str(selected_value) in table_data:
            rows = table_data[str(selected_value)]
            # We only have one amplitude from row["j_amp"], but the index is in row["x_j"]
            # If you want to plot them, you could parse or store a numeric index somewhere else
            # For now let's skip drawing them if we only store the index in text form
            # but let's assume we do store an integer "index" for plotting
            jxs, jys = [], []
            for row in rows:
                # x_j_str = row.get("x_j")    # e.g. "42 (2023-05-10 09:32:12.345)"
                j_amp = row.get("j_amp")
                idx_inte = row.get("idx_int", None)  # see finalize below
                x_j_str = index_to_timestamp(ts, 250, idx_inte)
                if j_amp is not None and idx_inte is not None:
                    # we can compute the actual time to display a marker
                    t_x = start_dt + timedelta(seconds=idx_inte*step_sec)
                    jxs.append(t_x)
                    jys.append(j_amp)

            if jxs:
                fig.add_trace(go.Scatter(
                    x=jxs, y=jys,
                    mode="markers",
                    marker_symbol="circle",
                    marker_color="darkorange", marker_size=10,
                    name="j-peaks (final)"
                ))

        # Partial j-peak if modeActive
        if annot_state and annot_state.get("modeActive"):
            j_samp_part = annot_state.get("j_samp")
            j_amp_part  = annot_state.get("j_amp")
            if j_samp_part is not None and j_amp_part is not None:
                xp = start_dt + timedelta(seconds=j_samp_part * step_sec)
                yp = j_amp_part
                fig.add_trace(go.Scatter(
                    x=[xp], y=[yp],
                    mode="markers",
                    marker_symbol="circle-open",
                    marker_color="darkorange", marker_size=10,
                    name="j (partial)",
                    hoverinfo="skip"
                ))

        fig.update_layout(
            title=f"Signal Start {start_dt} (Order={filter_order}, {lowcut}-{highcut}Hz)",
            xaxis_title="Time",
            yaxis_title="Amplitude",
            uirevision="signalPlot"
        )
        return fig

    #
    # 3) Done Signals
    #
    @app.callback(
        Output("done-signals-store", "data"),
        Output("signal-dropdown", "options"),
        Input("done-btn", "n_clicks"),
        State("signal-dropdown", "value"),
        State("done-signals-store", "data"),
        State("signal-dropdown", "options"),
        prevent_initial_call=True
    )
    def toggle_done(n_clicks, selected_value, done_list, current_options):
        if selected_value is None:
            return done_list, current_options
        if done_list is None:
            done_list = []
        if selected_value in done_list:
            done_list.remove(selected_value)
        else:
            done_list.append(selected_value)

        new_options = []
        for opt in current_options:
            lbl = opt["label"]
            val = opt["value"]
            if val in done_list and not lbl.startswith("✅ "):
                lbl = f"✅ {lbl}"
            elif val not in done_list and lbl.startswith("✅ "):
                lbl = lbl.replace("✅ ", "", 1)
            new_options.append({"label": lbl, "value": val})
        return done_list, new_options

    #
    # 4) Just toggling annotation mode
    #
    @app.callback(
        Output("annotation-store", "data"),
        Input("add-complex-btn", "n_clicks"),
        State("annotation-store", "data"),
        prevent_initial_call=True
    )
    def toggle_annotation_mode(n_clicks, annot_state):
        if annot_state is None:
            annot_state = {"modeActive": False}
        was_active = annot_state.get("modeActive", False)
        annot_state["modeActive"] = not was_active
        return annot_state

    #
    # 5) Restart => clear stores
    #
    @app.callback(
        Output("table-store", "data", allow_duplicate=True),
        Output("annotation-store", "data", allow_duplicate=True),
        Output("done-signals-store", "data", allow_duplicate=True),
        Input("restart-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def restart_app(n_clicks):
        return {}, {"modeActive": False}, []

    #
    # 6) Sync table deletions from DataTable => table-store
    #
    @app.callback(
        Output("table-store", "data", allow_duplicate=True),
        Input("complex-table", "data"),
        Input("complex-table", "data_previous"),
        State("signal-dropdown", "value"),
        State("table-store", "data"),
        prevent_initial_call=True
    )
    def sync_table_deletion(curr_data, prev_data,
                            selected_value, table_data):
        if table_data is None:
            table_data = {}
        if selected_value is None:
            return table_data
        # if curr_data == prev_data:
        #     return table_data\

        if prev_data is None or len(curr_data) >= len(prev_data):
            return dash.no_update

        str_idx = str(selected_value)
        if str_idx not in table_data:
            table_data[str_idx] = []
        table_data[str_idx] = curr_data
        return table_data

    #
    # 7) Data Export
    #
    @app.callback(
        Output("download-data-file", "data"),
        Input("export-btn", "n_clicks"),
        State("complex-table", "data"),
        State("export-format-dropdown", "value"),
        State("export-filename-input", "value"),
        prevent_initial_call=True
    )
    def export_table(n_clicks, table_data, export_format, base_name):
        if not table_data:
            return dash.no_update
        df = pd.DataFrame(table_data)
        if not base_name:
            base_name = "annotations"
        if export_format == "csv":
            filename = f"{base_name}.csv"
            return dcc.send_data_frame(df.to_csv, filename, index=False)
        else:
            return dash.no_update

    #
    # 8) Annotation Button (ON/OFF)
    #
    @app.callback(
        Output("add-complex-btn", "children"),
        Output("add-complex-btn", "style"),
        Input("annotation-store", "data")
    )
    def update_annotation_button(annot_state):
        if annot_state is None:
            annot_state = {"modeActive": False}
        if annot_state["modeActive"]:
            return (
                "Annotation Mode ON",
                {"backgroundColor": "green", "color": "white"}
            )
        else:
            return (
                "Annotation Mode OFF",
                {"backgroundColor": "red", "color": "white"}
            )

    #
    # 9) handle_plot_click => partial j-peak in peakInProgress
    #
    @app.callback(
        Output("peakInProgress", "data", allow_duplicate=True),
        Input("main-plot", "clickData"),
        State("annotation-store", "data"),
        State("signal-dropdown", "value"),
        State("peakInProgress", "data"),
        prevent_initial_call=True
    )
    def handle_plot_click(click_data, annot_state, selected_value, peak_in_progress):
        """
        If annotation mode is ON, store j_samp, j_amp in peakInProgress, set popUpOpen=True.
        We do NOT add row to table-store here => no double-add problem.
        """
        if peak_in_progress is None:
            peak_in_progress = {"popUpOpen": False}

        mode_on = annot_state.get("modeActive", False)
        if click_data and mode_on and selected_value is not None:
            from dateutil.parser import parse as dateparse
            time_str = click_data["points"][0]["x"]
            y_val = click_data["points"][0]["y"]

            entry = signals_data[selected_value]
            ts = entry["ts"]
            sig_vals = entry["signals"]
            num_samples = len(sig_vals)
            step_sec = duration/(num_samples-1) if num_samples>1 else 1
            start_dt = datetime.fromtimestamp(ts)
            dt_clicked = dateparse(time_str)
            delta_sec = (dt_clicked - start_dt).total_seconds()

            # float sample offset
            samp_float = delta_sec / step_sec if step_sec else 0
            # clamp to an integer in [0, num_samples-1]
            idx_int = max(0, min(int(round(samp_float)), num_samples - 1))

            # store partial in peakInProgress + open popup
            peak_in_progress = {
                "popUpOpen": True,
                "idx_int":   idx_int,   # store the integer index
                "y_amp":     y_val
            }
            return peak_in_progress
        
        return dash.no_update

    #
    # 9) Show/hide the pop-up
    #
    @app.callback(
        Output("modal-overlay", "style"),
        Input("peakInProgress", "data")
    )
    def toggle_overlay(peak_in_progress):
        if peak_in_progress is None:
            peak_in_progress = {}
        if peak_in_progress.get("popUpOpen", False):
            # Show overlay
            return {
                "display": "block",
                "position": "fixed",
                "top": 0, "left": 0,
                "width": "100%", "height": "100%",
                "backgroundColor": "rgba(0, 0, 0, 0.5)",
                "zIndex": 9998
            }
        else:
            return {"display": "none"}

    #
    # 9) finalize => add row to table-store w/ x_j label
    #
    @app.callback(
        Output("table-store", "data", allow_duplicate=True),
        Output("peakInProgress", "data", allow_duplicate=True),
        Input("confidence-done-btn", "n_clicks"),
        State("confidence-dropdown", "value"),
        State("peakInProgress", "data"),
        State("signal-dropdown", "value"),
        State("table-store", "data"),
        prevent_initial_call=True
    )
    def finalize_confidence(n_clicks, conf_val, peak_data, sel_val, table_data):
        """
        When user picks confidence + 'Done', finalize row in table-store:
         - x_j = "idx (timestamp)"
         - j_amp = amplitude
         - j_conf = chosen confidence
        Then close popup, reset partial
        """
        if table_data is None:
            table_data = {}
        if peak_data is None:
            peak_data = {"popUpOpen": False}

        if not conf_val:
            # user didn't pick any confidence => do nothing 
            return dash.no_update, dash.no_update

        idx_int  = peak_data.get("idx_int")
        y_amp    = peak_data.get("y_amp")
        pop_up   = peak_data.get("popUpOpen", False)
        if idx_int is None or y_amp is None or not pop_up:
            return dash.no_update, dash.no_update

        # Let's build a nice label "idx (timestamp)"
        # compute the timestamp from idx_int
        entry = signals_data[sel_val]
        ts = entry["ts"]
        sig_vals = entry["signals"]
        num_samples = len(sig_vals)
        step_sec = duration/(num_samples-1) if num_samples>1 else 1
        start_dt = datetime.fromtimestamp(ts)
        dt_for_idx = start_dt + timedelta(seconds=idx_int * step_sec)

        # Format a short string like "HH:MM:SS.fff"
        t_str = dt_for_idx.strftime("%H:%M:%S.%f")[:-3]  # remove last 3 for micro->milli
        x_j_str = f"{idx_int} ({t_str})"

        str_idx = str(sel_val)
        if str_idx not in table_data:
            table_data[str_idx] = []

        # build final row
        new_row = {
            "x_j": x_j_str,     # combined label
            "idx_int": idx_int, # optional numeric index for reference
            "j_amp":  y_amp,
            "j_conf": conf_val
        }
        table_data[str_idx].append(new_row)

        # close popup, reset partial
        updated_peak = {
            "popUpOpen": False,
            "idx_int": None,
            "y_amp":  None
        }

        return table_data, updated_peak

    #
    # 9) One-way store -> DataTable
    #
    @app.callback(
        Output("complex-table", "data"),
        Input("table-store", "data"),
        State("signal-dropdown", "value")
    )
    def update_table(table_data, selected_value):
        if not table_data or str(selected_value) not in table_data or selected_value is None:
            return []

        ts = signals_data[selected_value]["ts"]
        rows = table_data[str(selected_value)]
        table_rows = []

        for row in rows:
            idx_inte = row.get("idx_int")
            j_amp = row.get("j_amp")
            j_conf = row.get("j_conf")
            if ts is not None and idx_inte is not None:
                x_j_str = index_to_timestamp(ts, 250, idx_inte)
            else:
                x_j_str = "N/A"

            table_rows.append({
                "j_samp": x_j_str,  # Display the timestamp string
                "idx_int": idx_inte,
                "j_amp": j_amp,
                "j_conf": j_conf
            })
        return table_rows

    #
    # 10) Exit App
    #
    app.layout.children.append(dcc.Store(id="exit-trigger"))
    app.clientside_callback(
        dash.ClientsideFunction(namespace="clientside", function_name="close_window"),
        Output("exit-trigger", "data"),
        Input("exit-btn", "n_clicks"),
        prevent_initial_call=True
    )

    @app.callback(
        Output("exit-btn", "n_clicks"),
        Input("exit-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def exit_app(n_clicks):
        os._exit(0)
