import dash
from dash import Input, Output, State, ctx, dcc
from datetime import datetime, timedelta
import io
import pandas as pd
from parse_data import sos_filter
import plotly.graph_objects as go
import os
import warnings

warnings.simplefilter("ignore", category=UserWarning)

def register_callbacks(app, signals_data, duration):

    #
    # 1) Toggle the "dropdown" container's visibility
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
    # 2) Plot with final + partial annotations, dynamic filter, ECG mask, etc.
    #
    @app.callback(
        Output("main-plot", "figure"),
        [
            Input("signal-dropdown", "value"),
            Input("table-store", "data"),
            Input("annotation-store", "data"),

            # New dynamic filter inputs
            Input("filter-order-input", "value"),
            Input("lowcut-input", "value"),
            Input("highcut-input", "value")
        ]
    )
    def update_plot(
        selected_value,
        table_data,
        annot_state,
        filter_order,
        lowcut,
        highcut
    ):
        """
        Plots the selected signal, plus:
          - An ECG mask line if present
          - A dynamically filtered "helper" trace, using filter_order/lowcut/highcut
          - The raw signal
          - Final and partial annotation markers
        """
        fig = go.Figure()

        # 1) If no valid selection, just return a blank figure
        if selected_value is None or selected_value not in range(len(signals_data)):
            fig.update_layout(title="No Signal Selected", uirevision="signalPlot")
            return fig

        entry = signals_data[selected_value]
        ts = entry["ts"]
        signal_values = entry["signals"]
        ecg = entry.get("ecg", None)
        mask_arr = entry.get("mask", None)
        num_samples = len(signal_values)

        # 2) Create the x-axis
        start_dt = datetime.fromtimestamp(ts)
        step_sec = duration / (num_samples - 1) if num_samples > 1 else 1
        x_axis = [start_dt + timedelta(seconds=i * step_sec) for i in range(num_samples)]

        # 3) If there's a mask, build vertical lines at each index where mask==1
        if mask_arr is not None and len(mask_arr) == num_samples:
            y_min = min(signal_values)
            y_max = max(signal_values)
            x_mask = []
            y_mask = []
            for i, val in enumerate(mask_arr):
                if val == 1:
                    x_mask.extend([x_axis[i], x_axis[i], None])
                    y_mask.extend([y_min, y_max, None])
            if any(pt is not None for pt in x_mask):
                fig.add_trace(
                    go.Scatter(
                        x=x_mask,
                        y=y_mask,
                        mode="lines",
                        name="ECG Mask",
                        line=dict(color="blue", width=2),
                        opacity=0.7,
                        hoverinfo="skip",
                        showlegend=True
                    )
                )

        # 4) Raw signal trace
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=signal_values,
                name="Raw Signal",
                mode="lines",
                line=dict(color="black", width=2.5),
                hoverinfo="x+y"
            )
        )

        # 5) Filtered signal (dynamic)
        # The user sets filter_order, lowcut, highcut; we re-run sos_filter:
        if not filter_order:
            filter_order = 2
        if not lowcut:
            lowcut = 1.5
        if not highcut:
            highcut = 10.0

        filtered_signal = sos_filter(
            signal_values,
            order=filter_order,
            frequency_list=[lowcut, highcut],
            sample_rate=250
        )
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=filtered_signal,
                mode="lines",
                name="Filtered Signal",
                line=dict(color="red", width=2),
                opacity=0.66,
                hoverinfo="skip",
                showlegend=True
            )
        )

        # 6) If there's an 'ecg' array, render it
        if ecg is not None:
            fig.add_trace(
                go.Scatter(
                    x=x_axis,
                    y=ecg,
                    mode="lines",
                    name="ECG",
                    line=dict(color="green", width=2),
                    opacity=0.33,
                    hoverinfo="skip",
                    showlegend=True
                )
            )

        # 7) Plot final annotation markers from table-store
        if table_data and str(selected_value) in table_data:
            rows = table_data[str(selected_value)]
            i_x, i_y = [], []
            j_x, j_y = [], []
            k_x, k_y = [], []
            for row in rows:
                i_samp = row.get("i")
                j_samp = row.get("j")
                k_samp = row.get("k")

                if i_samp is not None:
                    xi = start_dt + timedelta(seconds=i_samp * step_sec)
                    idxi = clamp_index(int(round(i_samp)), 0, num_samples - 1)
                    yi = signal_values[idxi]
                    i_x.append(xi)
                    i_y.append(yi)
                if j_samp is not None:
                    xj = start_dt + timedelta(seconds=j_samp * step_sec)
                    idxj = clamp_index(int(round(j_samp)), 0, num_samples - 1)
                    yj = signal_values[idxj]
                    j_x.append(xj)
                    j_y.append(yj)
                if k_samp is not None:
                    xk = start_dt + timedelta(seconds=k_samp * step_sec)
                    idxk = clamp_index(int(round(k_samp)), 0, num_samples - 1)
                    yk = signal_values[idxk]
                    k_x.append(xk)
                    k_y.append(yk)

            # i, j, k final
            if i_x:
                fig.add_trace(go.Scatter(
                    x=i_x, y=i_y, mode="markers",
                    marker_symbol="x", marker_color="red",
                    marker_size=10, name="i markers"
                ))
            if j_x:
                fig.add_trace(go.Scatter(
                    x=j_x, y=j_y, mode="markers",
                    marker_symbol="circle", marker_color="blue",
                    marker_size=10, name="j markers"
                ))
            if k_x:
                fig.add_trace(go.Scatter(
                    x=k_x, y=k_y, mode="markers",
                    marker_symbol="triangle-up", marker_color="green",
                    marker_size=10, name="k markers"
                ))

        # 8) Render partial markers from annotation-store
        if annot_state:
            i_samp = annot_state.get("i_samp")
            i_amp = annot_state.get("i_amp")
            j_samp = annot_state.get("j_samp")
            j_amp = annot_state.get("j_amp")
            k_samp = annot_state.get("k_samp")
            k_amp = annot_state.get("k_amp")

            # partial i
            if i_samp is not None and i_amp is not None:
                xi = start_dt + timedelta(seconds=i_samp * step_sec)
                fig.add_trace(go.Scatter(
                    x=[xi], y=[i_amp],
                    mode="markers",
                    marker_symbol="x", marker_color="red",
                    marker_size=10, name="i (partial)",
                    hoverinfo="skip"
                ))
            # partial j
            if j_samp is not None and j_amp is not None:
                xj = start_dt + timedelta(seconds=j_samp * step_sec)
                fig.add_trace(go.Scatter(
                    x=[xj], y=[j_amp],
                    mode="markers",
                    marker_symbol="circle", marker_color="blue",
                    marker_size=10, name="j (partial)",
                    hoverinfo="skip"
                ))
            # partial k
            if k_samp is not None and k_amp is not None:
                xk = start_dt + timedelta(seconds=k_samp * step_sec)
                fig.add_trace(go.Scatter(
                    x=[xk], y=[k_amp],
                    mode="markers",
                    marker_symbol="triangle-up", marker_color="green",
                    marker_size=10, name="k (partial)",
                    hoverinfo="skip"
                ))

        # 9) Final layout
        fig.update_layout(
            title=f"Signal Starting {start_dt} (Order={filter_order}, "
                  f"{lowcut}-{highcut}Hz, Duration={duration}s)",
            xaxis_title="Time",
            yaxis_title="Amplitude",
            uirevision="signalPlot"
        )

        return fig

    def clamp_index(v, low, hi):
        return max(low, min(v, hi))

    #
    # 3) Toggle done signals
    #
    @app.callback(
        [Output("done-signals-store", "data"), Output("signal-dropdown", "options")],
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
            label_text = opt["label"]
            value = opt["value"]
            if value in done_list and not label_text.startswith("✅ "):
                label_text = f"✅ {label_text}"
            elif value not in done_list and label_text.startswith("✅ "):
                label_text = label_text.replace("✅ ", "", 1)
            new_options.append({"label": label_text, "value": value})
        return done_list, new_options

    #
    # 4) Handle annotation logic
    #
    @app.callback(
    Output("annotation-store", "data"),
    Output("table-store", "data"),
    Input("add-complex-btn", "n_clicks"),
    Input("main-plot", "clickData"),
    State("signal-dropdown", "value"),
    State("annotation-store", "data"),
    State("table-store", "data"),
    prevent_initial_call=True
)
    def handle_annotation(add_complex_clicks, click_data,
                        selected_signal, annot_state, table_data):
        """
        1) If "Add Complex" -> enter annotation mode (modeActive=True).
        2) If in annotation mode & user clicks -> record i->j->k sample offsets + amplitude.
        3) Once i, j, k are placed => compute width = x(k) - x(i), height = y(j) - y(k).
        Then store new row in table-store, exit annotation mode.
        """
        trigger_id = ctx.triggered_id

        if table_data is None:
            table_data = {}
        if annot_state is None:
            # We'll store both the offset (x) and amplitude (y) for each label
            annot_state = {
                "modeActive": False,
                "clickCount": 0,
                "i_samp": None, "i_amp": None,
                "j_samp": None, "j_amp": None,
                "k_samp": None, "k_amp": None
            }

        if selected_signal is None:
            return annot_state, table_data

        # Prepare a container for the current signal in table_data
        str_idx = str(selected_signal)
        if str_idx not in table_data:
            table_data[str_idx] = []

        # (A) If user clicked "Add Complex" => reset annotation
        if trigger_id == "add-complex-btn":
            annot_state = {
                "modeActive": True,
                "clickCount": 0,
                "i_samp": None, "i_amp": None,
                "j_samp": None, "j_amp": None,
                "k_samp": None, "k_amp": None
            }
            return annot_state, table_data

        # (B) If user clicks the plot while in annotation mode => place i, j, k
        if trigger_id == "main-plot" and annot_state.get("modeActive") and click_data:
            entry = signals_data[selected_signal]
            ts = entry["ts"]
            signal_values = entry["signals"]
            num_samples = len(signal_values)
            step_sec = duration / (num_samples - 1) if num_samples > 1 else 1

            from dateutil.parser import parse as dateparse
            time_str = click_data["points"][0]["x"]
            clicked_dt = dateparse(time_str)

            start_dt = datetime.fromtimestamp(ts)
            delta_sec = (clicked_dt - start_dt).total_seconds()
            sample_index_float = delta_sec / step_sec if step_sec != 0 else 0

            # We also store the amplitude at the clicked point
            amp_val = click_data["points"][0]["y"]

            seq = annot_state["clickCount"]
            if seq == 0:
                annot_state["i_samp"] = sample_index_float
                annot_state["i_amp"]  = amp_val
            elif seq == 1:
                annot_state["j_samp"] = sample_index_float
                annot_state["j_amp"]  = amp_val
            elif seq == 2:
                annot_state["k_samp"] = sample_index_float
                annot_state["k_amp"]  = amp_val

            annot_state["clickCount"] += 1

            # If we have placed i, j, k => finalize
            if annot_state["clickCount"] == 3:
                i_samp = annot_state["i_samp"]
                j_samp = annot_state["j_samp"]
                k_samp = annot_state["k_samp"]
                i_amp  = annot_state["i_amp"]
                j_amp  = annot_state["j_amp"]
                k_amp  = annot_state["k_amp"]

                # Now compute width, height as requested
                width  = k_samp - i_samp        # x(k) - x(i)
                height = j_amp - k_amp         # y(j) - y(k)

                new_row = {
                    "i": i_samp,
                    "j": j_samp,
                    "k": k_samp,
                    "width": width,
                    "height": height,
                    # other columns
                    "i_conf": "",
                    "j_conf": "",
                    "k_conf": ""
                }
                table_data[str_idx].append(new_row)

                # reset annotation
                annot_state = {
                    "modeActive": False,
                    "clickCount": 0,
                    "i_samp": None, "i_amp": None,
                    "j_samp": None, "j_amp": None,
                    "k_samp": None, "k_amp": None
                }

            return annot_state, table_data

        # No action
        return annot_state, table_data


    #
    # 5) DataTable in sync with table-store
    #
    @app.callback(
        Output("complex-table", "data"),
        Input("table-store", "data"),
        State("signal-dropdown", "value")
    )
    def update_table(table_data, selected_signal):
        if not table_data or selected_signal is None:
            return []
        str_idx = str(selected_signal)
        if str_idx not in table_data:
            return []
        return table_data[str_idx]

    #
    # 6) Exit App
    #
    app.layout.children.append(dcc.Store(id="exit-trigger"))
    app.clientside_callback(
        dash.ClientsideFunction(namespace="clientside", function_name="close_window"),
        Output("exit-trigger", "data"),
        Input("exit-btn", "n_clicks"),
        prevent_initial_call=True
    )

    @app.callback(
    Output("history-store", "data", allow_duplicate=True),
    Output("table-store", "data", allow_duplicate=True),
    Output("annotation-store", "data", allow_duplicate=True),
    Input("table-store", "data"),               # or annotation-store, or both
    Input("annotation-store", "data"),
    Input("undo-btn", "n_clicks"),
    Input("redo-btn", "n_clicks"),
    State("history-store", "data"),
    prevent_initial_call=True
)
    def manage_history(table_data, annot_data, undo_click, redo_click, history):
        if history is None:
            history = {
                "past": [],
                "present": {"table": {}, "annot": {}},
                "future": []
            }

        past = history["past"]
        present = history["present"]
        future = history["future"]

        def return_no_change():
            # Ensure 'table' and 'annot' exist in present
            if "table" not in present:
                present["table"] = {}
            if "annot" not in present:
                present["annot"] = {}
            return history, present["table"], present["annot"]

        triggered_id = ctx.triggered_id

        if triggered_id == "undo-btn":
            if len(past) > 0:
                future.append(present)
                new_present = past.pop()
                return {
                    "past": past,
                    "present": new_present,
                    "future": future
                }, new_present["table"], new_present["annot"]
            else:
                return return_no_change()

        elif triggered_id == "redo-btn":
            if len(future) > 0:
                past.append(present)
                new_present = future.pop()
                return {
                    "past": past,
                    "present": new_present,
                    "future": future
                }, new_present["table"], new_present["annot"]
            else:
                return return_no_change()

        else:
            # some new user action updating table_data / annot_data
            # if it differs from present, push old present to past, set new present
            if table_data != present.get("table") or annot_data != present.get("annot"):
                past.append(present)
                new_present = {"table": table_data, "annot": annot_data}
                return {
                    "past": past,
                    "present": new_present,
                    "future": []
                }, table_data, annot_data

            # otherwise no real change
            return return_no_change()



    @app.callback(
    Output("table-store", "data", allow_duplicate=True),
    Input("complex-table", "data"),
    Input("complex-table", "data_previous"),
    State("signal-dropdown", "value"),
    State("table-store", "data"),
    prevent_initial_call=True
)
    def sync_table_deletion(curr_data, prev_data, selected_signal, table_data):
        """
        If the user deletes a row in the DataTable,
        remove that row from table-store => markers vanish from the plot.
        """
        if table_data is None:
            table_data = {}

        # If no signal selected, do nothing
        if selected_signal is None:
            return table_data

        # If user didn't actually delete or change rows, do nothing
        if curr_data == prev_data:
            return table_data

        str_idx = str(selected_signal)

        # Make sure we have a valid entry in table_data
        if str_idx not in table_data:
            table_data[str_idx] = []

        # The DataTable 'curr_data' is the new set of rows after deletion
        # so just set table_data[str_idx] to match
        table_data[str_idx] = curr_data
        return table_data
    
    @app.callback(
        Output("download-data-file", "data"),
        Input("export-btn", "n_clicks"),
        State("complex-table", "data"),
        State("export-format-dropdown", "value"),
        State("export-filename-input", "value"),
        prevent_initial_call=True
    )
    def export_table(n_clicks, table_data, export_format, base_name):
        """
        Exports the current annotation table to the chosen format:
        CSV, Excel, Parquet, or Pickle.
        """

        if not table_data:
            # No rows => do nothing
            return dash.no_update

        # Convert table_data (list of dicts) => pandas DataFrame
        df = pd.DataFrame(table_data)

        if not base_name:
            base_name = "annotations"

        if export_format == "csv":
            # Use dash's send_data_frame
            filename = f"{base_name}.csv"
            return dcc.send_data_frame(df.to_csv, filename, index=False)

        # elif export_format == "excel":
        #     filename = f"{base_name}.xlsx"
        #     return dcc.send_data_frame(
        #         df.to_excel, filename, sheet_name="Annotations", index=False
        # )

        # elif export_format == "parquet":
        #     # There's no built-in "send_parquet" yet, so we do a BytesIO approach
        #     filename = f"{base_name}.parquet"
        #     buf = io.BytesIO()
        #     df.to_parquet(buf, index=False)
        #     buf.seek(0)
        #     return dcc.send_bytes(buf.read, filename)

        # elif export_format == "pickle":
        #     # Similarly, we do send_bytes
        #     filename = f"{base_name}.pkl"
        #     buf = io.BytesIO()
        #     df.to_pickle(buf)
        #     buf.seek(0)
        #     return dcc.send_bytes(buf.read, filename)

        else:
            # unknown format => do nothing
            return dash.no_update


    @app.callback(
        Output("exit-btn", "n_clicks"),
        Input("exit-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def exit_app(n_clicks):
        os._exit(0)
