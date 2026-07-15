import viktor as vkt


class Parametrization(vkt.Parametrization):
    introduction = vkt.Text(
        "# Revit 2025 → BHoM\n"
        "Read the active Revit model through the configured Windows worker, "
        "inspect its BHoM geometry and metadata, and prepare its material takeoff "
        "for the downstream mapping app."
    )

    categories = vkt.MultiSelectField(
        "Revit categories",
        options=[
            "Walls",
            "Floors",
            "Structural Columns",
            "Structural Framing",
            "Roofs",
        ],
        default=["Walls", "Floors", "Structural Columns"],
        description="Choose the model elements to read through the BHoM Revit adapter.",
    )
    br1 = vkt.LineBreak()
    include_parameters = vkt.BooleanField(
        "Include Revit parameters",
        default=True,
        description="Include instance and type properties in the model metadata.",
    )
    element_limit = vkt.IntegerField(
        "Maximum elements",
        min=1,
        max=10000,
        default=2500,
        description="Safety limit for one worker request.",
    )

    takeoff_description = vkt.Text(
        "## Material takeoff\n"
        "The LCA data view audits material quantities and available densities. "
        "EPD mapping and life-cycle module selection belong to the downstream apps."
    )

    exports_description = vkt.Text(
        "## Exports\n"
        "Download the normalized material takeoff or the raw BHoM model objects."
    )
    download_takeoff = vkt.DownloadButton(
        "Download BHoM takeoff",
        method="download_takeoff",
        longpoll=True,
    )
    br2 = vkt.LineBreak()
    download_snapshot = vkt.DownloadButton(
        "Download raw BHoM snapshot",
        method="download_snapshot",
        longpoll=True,
    )
