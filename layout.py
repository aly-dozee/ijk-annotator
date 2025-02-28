from dash import html, dcc, dash_table
from datetime import datetime
import warnings

warnings.simplefilter("ignore", category=UserWarning)

def create_layout(signals_data, path_to_file):
    dropdown_options = [
        {
            "label": datetime.fromtimestamp(int(entry["ts"])).strftime("%Y-%m-%d %H:%M:%S"),
            "value": i
        }
        for i, entry in enumerate(signals_data)
    ]

    layout = html.Div(
        style={"display": "flex", "flexDirection": "column", "height": "100vh"},
        children=[
            # Header Section
            html.Div(
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                    "height": "60px",
                    "padding": "0 10px",
                    "backgroundColor": "#f2f2f2",
                    "borderBottom": "1px solid #ccc"
                },
                children=[
                    html.Button("Restart", id="restart-btn", n_clicks=0),
                    dcc.Dropdown(
                        id="signal-dropdown",
                        options=dropdown_options,
                        value=None,
                        placeholder="Select a signal",
                        style={"width": "375px"}
                    ),
                    html.Button("Done", id="done-btn", n_clicks=0),
                    html.Button("Exit", id="exit-btn", n_clicks=0)
                ]
            ),

            # Main Plot + hidden stores
            html.Div(
                style={"flex": 1, "padding": "10px"},
                children=[
                    dcc.Graph(
                        id="main-plot",
                        figure={},
                        style={"width": "100%", "height": "100%"},
                        config={"displayModeBar": True},
                    ),

                    # Hidden data stores
                    dcc.Store(id="table-store", data={}),
                    dcc.Store(id="done-signals-store", data=[]),
                    dcc.Store(
                        id="annotation-store",
                        data={
                            "activeLabel": None,  # which label user is placing next: i/j/k
                            # "i_samp": None, "i_amp": None,
                            "j_samp": None, "j_amp": None,
                            # "k_samp": None, "k_amp": None,
                            "preview_samp": None, "preview_amp": None,
                            "modeActive": False,
                        }
                    ),
                    dcc.Store(id="peakInProgress", data={"popUpOpen": False}),
                ]
            ),

            # Overlay that covers the entire screen
            html.Div(
                id="modal-overlay",
                style={
                    "display": "none",             # hidden by default
                    "position": "fixed",
                    "top": 0, "left": 0,
                    "width": "100%", "height": "100%",
                    "backgroundColor": "rgba(0, 0, 0, 0.5)", # semi-transparent background
                    "zIndex": 9998                  # behind the modal content
                },
                children=[
                    # The "modal" content inside the overlay
                    html.Div(
                        id="confidence-modal",
                        style={
                            "position": "absolute",
                            "top": "50%", "left": "50%",
                            "transform": "translate(-50%, -50%)",
                            "backgroundColor": "white",
                            "padding": "20px",
                            "border": "2px solid #ccc",
                            "zIndex": 9999,  # above the overlay background
                        },
                        children=[
                            html.H3("Select Confidence for this Peak"),
                            dcc.Dropdown(
                                id="confidence-dropdown",
                                options=[
                                    {"label": "Unsure",         "value": "Unsure"},
                                    {"label": "Somewhat Sure",  "value": "Somewhat Sure"},
                                    {"label": "Sure",           "value": "Sure"}
                                ],
                                placeholder="Pick confidence..."
                            ),
                            html.Button("Done", id="confidence-done-btn", n_clicks=0, style={"marginTop": "10px"}),
                        ]
                    )
                ]
            ),

            # Table + Buttons Section
            html.Div(
                style={"padding": "10px"},
                children=[
                    # The label-choosing buttons
                    html.Div(
                        style={"display": "flex", "flexDirection": "row", "gap": "10px", "marginBottom": "10px"},
                        children=[
                            html.Button("Annotation Mode OFF", id="add-complex-btn", n_clicks=0),
                        ]
                    ),

                    # Filter toolbar for dynamic filter settings
                    html.Div(
                        style={"display": "flex", "flexDirection": "row", "gap": "10px", "marginBottom": "10px"},
                        children=[
                            html.Label("Filter Order:"),
                            dcc.Input(
                                id="filter-order-input",
                                type="number",
                                value=2,        # default
                                min=1,
                                max=10,
                                step=1,
                                style={"width": "60px"}
                            ),
                            html.Label("Low Freq:"),
                            dcc.Input(
                                id="lowcut-input",
                                type="number",
                                value=5.0,      # default
                                step=0.5,
                                style={"width": "60px"}
                            ),
                            html.Label("High Freq:"),
                            dcc.Input(
                                id="highcut-input",
                                type="number",
                                value=15.0,     # default
                                step=0.5,
                                style={"width": "60px"}
                            ),
                        ]
                    ),

                    # DataTable for complex
                    dash_table.DataTable(
                        id="complex-table",
                        columns=[
                            {
                                "name": "x_j (timestamp)",
                                "id": "j_samp",
                                "type": "text"
                            },
                            {
                                "name": "x_j (index)",
                                "id": "idx_int",
                                "type": "numeric"
                            },
                            {
                                "name": "y_j",
                                "id": "j_amp",
                                "type": "numeric"
                            },
                            {
                                "name": "j_conf",
                                "id": "j_conf",
                                "type": "text"
                            }
                        ],
                        data=[],
                        editable=True,
                        row_deletable=True,
                        dropdown={
                            "j_conf": {
                                "options": [
                                    {"label": "Unsure",         "value": "Unsure"},
                                    {"label": "Somewhat Sure",  "value": "Somewhat Sure"},
                                    {"label": "Sure",           "value": "Sure"}
                                ],
                                "clearable": True
                            }
                        }
                    ),

                    # Export controls
                    html.Div(
                        style={"display": "flex", "flexDirection": "row", "gap": "10px", "marginTop": "20px"},
                        children=[
                            dcc.Input(
                                id="export-filename-input",
                                type="text",
                                value="annotations",
                                style={"width": "150px"}
                            ),
                            dcc.Dropdown(
                                id="export-format-dropdown",
                                options=[
                                    {"label": "CSV", "value": "csv"},
                                ],
                                value="csv",
                                style={"width": "120px"}
                            ),
                            html.Button("Export", id="export-btn", n_clicks=0),
                        ]
                    ),
                    dcc.Download(id="download-data-file"),
                ]
            ),
        ]
    )

    return layout