import viktor as vkt


class Parametrization(vkt.Parametrization):
    introduction = vkt.Text(
        "# BHoM material template mapping\n"
        "Map each source material to an installed BHoM EPD and create a reusable "
        "BHoM material template. The optional workflow handoff can then package "
        "that template with the takeoff and project area for downstream processing."
    )

    takeoff_file = vkt.FileField(
        "BHoM takeoff (Optional)",
        file_types=[".json"],
        max_size=20_000_000,
        description=(
            "Optional: upload a GeneralMaterialTakeoff exported by the Revit app, "
            "or leave it empty and use or edit the material table instead."
        ),
    )
    br1 = vkt.LineBreak()
    dataset_scope = vkt.OptionField(
        "Installed dataset scope",
        options=[
            "All installed LCA datasets",
            "ICE",
            "Boverket",
            "EC3 snapshots",
            "EPiC",
            "Oekobaudat",
        ],
        default="All installed LCA datasets",
        description=(
            "Limits the search to a BHoM LifeCycleAssessment library path. "
            "No external API or token is used."
        ),
    )
    br2 = vkt.LineBreak()
    gross_floor_area_m2 = vkt.NumberField(
        "Gross floor area",
        min=0,
        default=0,
        suffix=" m²",
        num_decimals=2,
        description=(
            "Included only in the optional Workflow handoff for downstream "
            "processing; it does not change the standalone material template."
        ),
    )

    inventory_help = vkt.Text(
        "## Material inventory\n"
        "Upload a Revit takeoff or edit the table. Use **Search query** to refine "
        "the installed BHoM dataset lookup; when blank, the material name is used."
    )
    material_inventory = vkt.Table(
        "Materials",
        default=[
            {
                "material_name": "Concrete C30/37",
                "search_query": "ready mix concrete C30/37",
                "volume_m3": 32.0,
                "density_kg_m3": 2400.0,
            },
            {
                "material_name": "Structural Steel",
                "search_query": "structural steel",
                "volume_m3": 0.4,
                "density_kg_m3": 7850.0,
            },
        ],
        description="One row per Revit source material.",
    )
    material_inventory.material_name = vkt.TextField("Material")
    material_inventory.search_query = vkt.TextField("Search query")
    material_inventory.volume_m3 = vkt.NumberField(
        "Volume",
        suffix=" m³",
        num_decimals=3,
    )
    material_inventory.density_kg_m3 = vkt.NumberField(
        "Density",
        suffix=" kg/m³",
        num_decimals=1,
    )
    br3 = vkt.LineBreak()
    search_database = vkt.SetParamsButton(
        "Search installed BHoM datasets",
        method="search_bhom_database",
        longpoll=True,
        description=(
            "Runs BHoM Library_Engine through the Windows Generic Worker and "
            "populates the Mapping view with typed EPDs."
        ),
    )

    mapping_help = vkt.Text(
        "## Results and Excel export\n"
        "**Mapping** chooses one installed dataset result per source material. "
        "**Material template** remains the reusable standalone result, while "
        "**Workflow handoff** remains the optional integration envelope. Export one "
        "workbook containing the canonical material template, normalized takeoff, and "
        "workflow handoff payloads."
    )
    download_excel = vkt.DownloadButton(
        "Export Excel",
        method="download_excel",
    )
    br4 = vkt.LineBreak()

    takeoff_json = vkt.TextAreaField(
        "Takeoff JSON",
        default="",
        visible=False,
    )
    lookup_results_json = vkt.TextAreaField(
        "BHoM lookup results JSON",
        default="",
        visible=False,
    )
    mapping_state_json = vkt.TextAreaField(
        "Mapping state JSON",
        default='{"schema_version":"1.0","mappings":{}}',
        visible=False,
    )
    template_materials_json = vkt.TextAreaField(
        "Template materials JSON",
        default="[]",
        visible=False,
    )
