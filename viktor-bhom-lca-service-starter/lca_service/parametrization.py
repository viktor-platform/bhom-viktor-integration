import viktor as vkt


class Parametrization(vkt.Parametrization):
    introduction = vkt.Text(
        "# BHoM life-cycle assessment service\n"
        "Upload a BHoM material takeoff and template materials, or provide "
        "the JSON inline for a remote entity computation. The calculation "
        "runs on the registered `bhom_lca` Generic Worker executable.\n\n"
        "For the selected modules, the reported impact is calculated as "
        "$GWP = \\sum_i m_i \\sum_s f_{i,s}$, where $m_i$ is material "
        "mass and $f_{i,s}$ is the verified factor for life-cycle stage "
        "$s$.\n\n"
        "**Data notice:** bundled factors are synthetic test data and are "
        "not approved for project reporting."
    )

    project_id = vkt.TextField(
        "Project ID",
        default="sample-office",
    )
    project_name = vkt.TextField(
        "Project name",
        default="Sample Office",
    )
    gross_floor_area_m2 = vkt.NumberField(
        "Gross floor area",
        suffix=" m²",
        min=0,
        default=500.0,
        description="Used to calculate the project carbon intensity.",
    )

    takeoff_file = vkt.FileField(
        "BHoM takeoff JSON",
        file_types=[".json"],
        description=("One serialized BH.oM.Physical.Materials.GeneralMaterialTakeoff."),
    )
    template_materials_file = vkt.FileField(
        "BHoM template-material JSON",
        file_types=[".json"],
        description=("A JSON array of BH.oM.Physical.Materials.Material objects."),
    )

    takeoff_json = vkt.TextAreaField(
        "Inline BHoM takeoff JSON",
        description=(
            "Used when no takeoff file is uploaded. Suitable for API tests "
            "and small payloads."
        ),
    )
    template_materials_json = vkt.TextAreaField(
        "Inline BHoM template-material JSON",
        description=(
            "Used when no template file is uploaded. Suitable for API tests "
            "and small payloads."
        ),
    )

    prioritise_template_materials = vkt.BooleanField(
        "Prioritise template materials",
        default=True,
        description=(
            "Use matching uploaded template EPDs before properties already "
            "present on takeoff materials."
        ),
    )
    modules = vkt.MultiSelectField(
        "Life-cycle modules",
        options=["A1", "A2", "A3", "A1toA3"],
        default=["A1", "A2", "A3"],
        description=("Do not combine A1toA3 with A1, A2 or A3."),
    )

    chart_type = vkt.OptionField(
        "Chart type",
        options=["Bar", "Stacked bar", "Treemap", "Sunburst"],
        default="Stacked bar",
    )
    group_by = vkt.OptionField(
        "Group by",
        options=["Material", "EPD", "Module"],
        default="Material",
    )

    run_and_download = vkt.DownloadButton(
        "Run and download normalized JSON",
        method="run_analysis",
        longpoll=True,
    )
    download_raw = vkt.DownloadButton(
        "Download raw BHoM results",
        method="download_raw_bhom",
        longpoll=True,
    )
    download_events_button = vkt.DownloadButton(
        "Download analysis events",
        method="download_events",
        longpoll=True,
    )
    download_runtime_button = vkt.DownloadButton(
        "Download runtime manifest",
        method="download_runtime_manifest",
        longpoll=True,
    )
