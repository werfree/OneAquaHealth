"""OAH Indicators model.

Source: oah/input/fsh/model-maps/IndicatorsOah.fsh
Maps to (via IndicatorsOah2FHIR.fsh): observation-indicators-oah, observation-with-component-oah.

Leaves typed `SimpleIndicator`/`StructuredIndicator` in the source FSH reuse
those logical models directly. Leaves typed the abstract `Base` (i.e. not yet
modeled in detail by the IG) use `GenericIndicatorMeasure` as a placeholder --
see common.py.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .common import GenericIndicatorMeasure
from .simple_indicator import SimpleIndicatorOah
from .structured_indicator import StructuredIndicatorOah


class BiologicalIndicators(BaseModel):
    """`IndicatorsOah.biological` -- biological quality indicators."""

    macroinvertebreates: List[SimpleIndicatorOah] = Field(default_factory=list, description="Benthic Macroinvertebrates.")
    diatomes: List[SimpleIndicatorOah] = Field(default_factory=list, description="Diatoms (microalgae/phytobenthos).")
    fishes: List[SimpleIndicatorOah] = Field(default_factory=list, description="Fish-related measures.")
    macrophytes: List[StructuredIndicatorOah] = Field(default_factory=list, description="Macrophytes (aquatic plants).")
    riparianVegetation: List[StructuredIndicatorOah] = Field(default_factory=list, description="Riparian vegetation.")
    microbiomes: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Microbiomes/Biofilms.")


class HydromorphologicalIndicators(BaseModel):
    """`IndicatorsOah.hydromorphological` -- habitat/channel/land-use indicators."""

    morphology: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Morphology of the streams.")
    hydrology: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Hydrology of the stream.")
    landUse: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Land use in the margins.")


class WaterIndicators(BaseModel):
    """`IndicatorsOah.water` -- water physical/chemical quality indicators."""

    nutrients: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Nitrates, nitrites, ammonia, phosphates, total P/N.")
    pH: List[GenericIndicatorMeasure] = Field(default_factory=list)
    dissolvedO2: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Dissolved O2.")
    waterTemperature: List[GenericIndicatorMeasure] = Field(default_factory=list)
    tds: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Total dissolved solids.")
    tss: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Total suspended solids.")
    conductivity: List[GenericIndicatorMeasure] = Field(default_factory=list)
    pharmaceuticals: List[GenericIndicatorMeasure] = Field(default_factory=list)
    foam: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Foam/colour/smell.")
    coliforms: List[GenericIndicatorMeasure] = Field(default_factory=list)


class BioRiskIndicators(BaseModel):
    """`IndicatorsOah.bioRisk` -- biological indicators of health risk."""

    diptera: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Culicidae and Psycodidae.")
    ticks: List[GenericIndicatorMeasure] = Field(default_factory=list)
    invasiveOrganisms: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Invasive invertebrate, plants and fish.")
    birds: List[GenericIndicatorMeasure] = Field(default_factory=list)
    diatomTratology: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Diatom teratology (deformities).")
    fish: List[GenericIndicatorMeasure] = Field(default_factory=list)
    amphibians: List[GenericIndicatorMeasure] = Field(default_factory=list)


class RemoteSensingIndicators(BaseModel):
    """`IndicatorsOah.remote` -- satellite/UAV/airborne reflectance-derived indices."""

    ndci: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Normalized Difference Chlorophyll Index.")
    mci: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Maximum Chlorophyll Index.")
    bwdrvi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Blue Wide Dynamic Range Vegetation Index.")
    evi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Enhanced Vegetation Index.")
    evi2: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Enhanced Vegetation Index 2.")
    ndvi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Normalized Difference Vegetation Index.")
    mndvi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Modified NDVI.")
    ndwi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Normalized Difference Water Index.")
    savi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Soil Adjusted Vegetation Index.")
    tsavi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Transformed SAVI.")
    lwci: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Leaf Water Content Index.")
    gvmi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Global Vegetation Moisture Index.")
    gemi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Global Environment Monitoring Index.")
    lai: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Leaf Area Index.")
    glai: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Green Leaf Area Index.")
    fapar: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Fraction of Absorbed PAR.")
    mndwi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Modified NDWI.")
    andwi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Augmented NDWI.")
    s2wi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Sentinel-2 Water Index.")
    lswi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Land Surface Water Index.")
    ndviMndwiModel: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Combined NDVI-MNDWI model.")
    lst: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Land Surface Temperature.")
    blfei: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Built-Up Land Features Extraction Index.")
    brba: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Band Ratio for Built-up Area.")
    nbai: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Normalized Built-up Area Index.")
    ibi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Index-Based Built-Up Index.")
    ebbi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Enhanced Built-Up and Bareness Index.")
    pisi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Perpendicular Impervious Surface Index.")
    ui: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Urban Index.")
    vibi: List[GenericIndicatorMeasure] = Field(default_factory=list, description="Vegetation Index Built-up Index.")


class IndicatorsOah(BaseModel):
    """OAH Indicators: the environmental indicator catalogue used across the project."""

    biological: Optional[BiologicalIndicators] = Field(None, description="0..1. Biological quality indicators.")
    hydromorphological: Optional[HydromorphologicalIndicators] = Field(None, description="0..1. Hydromorphological quality indicators.")
    water: Optional[WaterIndicators] = Field(None, description="0..1. Water quality indicators.")
    bioRisk: Optional[BioRiskIndicators] = Field(None, description="0..1. Biological indicators of health risk.")
    remote: Optional[RemoteSensingIndicators] = Field(None, description="0..1. Remote sensing indices.")
