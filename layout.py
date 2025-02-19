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
                    # All your hidden stores:
                    dcc.Store(id="table-store", data={}),
                    dcc.Store(id="done-signals-store", data=[]),
                    dcc.Store(
                        id="annotation-store",
                        data={
                            "activeLabel": None,  # which label user is placing next: "i"/"j"/"k"
                            "i_samp": None, "i_amp": None,  # x offset + amplitude for i
                            "j_samp": None, "j_amp": None,  # x offset + amplitude for j
                            "k_samp": None, "k_amp": None,  # x offset + amplitude for k
                            "preview_samp": None, "preview_amp": None,  # for hover preview
                            "modeActive": False,  # if you only allow annotation after "Add Complex"? 
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
                            # Add Complex is only enabled if i, j, k all placed
                            html.Button("Add Complex", id="add-complex-btn", n_clicks=0),
                        ]
                    ),

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
                    # 1) Export format dropdown + export button
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
                                    # {"label": "Excel", "value": "excel"},
                                    # {"label": "Parquet", "value": "parquet"},
                                    # {"label": "Pickle", "value": "pickle"}
                                ],
                                value="csv",  # default
                                style={"width": "120px"}
                            ),
                            html.Button("Export", id="export-btn", n_clicks=0),
                        ]
                    ),

                    # 2) The Download component for generating the file
                    dcc.Download(id="download-data-file"),
                ]
            ),
        ]
    )

    return layout
