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
                    html.Button("Undo", id="undo-btn", n_clicks=0),
                    html.Button("Redo", id="redo-btn", n_clicks=0),
                    dcc.Dropdown(
                        id="signal-dropdown",
                        options=dropdown_options,
                        value=None,
                        placeholder="Select a signal",
                        style={"width": "250px"}
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
                        id="history-store",
                        data={
                            "past": [],
                            "present": {
                                "table": {},
                                "annot": {}
                            },
                            "future": []
                        }
                    ),
                    dcc.Store(
                        id="annotation-store",
                        data={
                            "activeLabel": None,  # which label user is placing next: "i"/"j"/"k"
                            "i_samp": None, "i_amp": None,
                            "j_samp": None, "j_amp": None,
                            "k_samp": None, "k_amp": None,
                            "preview_samp": None, "preview_amp": None,
                            "modeActive": False,
                        }
                    ),
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
                            html.Button("i", id="i-btn", n_clicks=0),
                            html.Button("j", id="j-btn", n_clicks=0),
                            html.Button("k", id="k-btn", n_clicks=0),
                            html.Button("Add Complex", id="add-complex-btn", n_clicks=0),
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
                                value=1.5,      # default
                                step=0.5,
                                style={"width": "60px"}
                            ),
                            html.Label("High Freq:"),
                            dcc.Input(
                                id="highcut-input",
                                type="number",
                                value=10.0,     # default
                                step=0.5,
                                style={"width": "60px"}
                            ),
                        ]
                    ),

                    # DataTable for complex
                    dash_table.DataTable(
                        id="complex-table",
                        columns=[
                            {"name": "i", "id": "i", "type": "numeric"},
                            {"name": "i_conf", "id": "i_conf", "presentation": "dropdown"},
                            {"name": "j", "id": "j", "type": "numeric"},
                            {"name": "j_conf", "id": "j_conf", "presentation": "dropdown"},
                            {"name": "k", "id": "k", "type": "numeric"},
                            {"name": "k_conf", "id": "k_conf", "presentation": "dropdown"},
                            {"name": "height", "id": "height", "type": "numeric"},
                            {"name": "width", "id": "width", "type": "numeric"},
                        ],
                        data=[],
                        editable=True,
                        row_deletable=True,
                        dropdown={
                            "i_conf": {
                                "options": [
                                    {"label": "Unsure", "value": "Unsure"},
                                    {"label": "Low", "value": "Low"},
                                    {"label": "Medium", "value": "Medium"},
                                    {"label": "High", "value": "High"}
                                ]
                            },
                            "j_conf": {
                                "options": [
                                    {"label": "Unsure", "value": "Unsure"},
                                    {"label": "Low", "value": "Low"},
                                    {"label": "Medium", "value": "Medium"},
                                    {"label": "High", "value": "High"}
                                ]
                            },
                            "k_conf": {
                                "options": [
                                    {"label": "Unsure", "value": "Unsure"},
                                    {"label": "Low", "value": "Low"},
                                    {"label": "Medium", "value": "Medium"},
                                    {"label": "High", "value": "High"}
                                ]
                            }
                        },
                        style_table={"width": "100%", "overflowX": "auto"},
                        style_header={"backgroundColor": "#f2f2f2", "fontWeight": "bold"},
                        style_cell={"padding": "8px", "textAlign": "center"}
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