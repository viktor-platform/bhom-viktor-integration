import viktor as vkt


class Parametrization(vkt.Parametrization):
    introduction = vkt.Text(
        "# Revit 2025 → BHoM model gateway\n"
        "Pull a read-only model snapshot through a fixed Windows worker, inspect "
        "Revit metadata, and build the exact `GeneralMaterialTakeoff` payload used "
        "by the BHoM LCA service. Start with the bundled sample; switch to the "
        "worker only after Revit 2025 and the BHoM listener are running.\n\n"
        "**Boundary:** this app reads model data. It does not push changes into "
        "Revit and it never accepts DLL paths, socket ports, or arbitrary BHoM "
        "method names."
    )

    source = vkt.Section("Model source")
    source.connection_mode = vkt.OptionField(
        "Connection mode",
        options=["Bundled sample", "Revit 2025 worker"],
        default="Bundled sample",
        description=(
            "The worker uses the fixed 'bhom_revit' executable on the Windows "
            "machine that hosts Revit."
        ),
    )
    source.document_name = vkt.TextField(
        "Expected document name",
        default="Sample Office 2025.rvt",
        description=(
            "Optional guard. The gateway rejects a different active document "
            "instead of silently reading the wrong model."
        ),
    )
    source.categories = vkt.MultiSelectField(
        "Revit categories",
        options=[
            "Walls",
            "Floors",
            "Structural Columns",
            "Structural Framing",
            "Roofs",
        ],
        default=["Walls", "Floors", "Structural Columns"],
        description="The gateway maps these allow-listed names to Revit filters.",
    )
    source.include_parameters = vkt.BooleanField(
        "Include pulled parameters",
        default=True,
        description=(
            "Preserve instance/type metadata from RevitPulledParameters for the "
            "metadata view."
        ),
    )
    source.element_limit = vkt.IntegerField(
        "Maximum elements",
        min=1,
        max=10000,
        default=2500,
        description="Safety limit for one interactive snapshot.",
    )

    project = vkt.Section("LCA handoff")
    project.project_id = vkt.TextField(
        "Project ID",
        default="sample-office-revit-2025",
    )
    project.project_name = vkt.TextField(
        "Project name",
        default="Sample Office — Revit 2025",
    )
    project.gross_floor_area_m2 = vkt.NumberField(
        "Gross floor area",
        suffix=" m²",
        min=0,
        default=500.0,
        description="Passed unchanged to the carbon-analysis service.",
    )
    project.template_materials_file = vkt.FileField(
        "Production BHoM template materials",
        file_types=[".json"],
        description=(
            "Optional BHoM Material array with approved EPDs. If omitted, the "
            "handoff uses bundled synthetic test factors."
        ),
    )
    project.modules = vkt.MultiSelectField(
        "Life-cycle modules",
        options=["A1", "A2", "A3", "A1toA3"],
        default=["A1", "A2", "A3"],
        description="Do not combine A1toA3 with A1, A2, or A3.",
    )

    actions = vkt.Section("Exports")
    actions.download_takeoff = vkt.DownloadButton(
        "Download BHoM takeoff",
        method="download_takeoff",
        longpoll=True,
    )
    actions.download_snapshot = vkt.DownloadButton(
        "Download raw BHoM snapshot",
        method="download_snapshot",
        longpoll=True,
    )
    actions.download_lca_handoff = vkt.DownloadButton(
        "Build carbon-analysis handoff",
        method="download_lca_handoff",
        longpoll=True,
    )
