"""Display text for the `Observation.code` of every OAH-generic-leaf indicator.

`IndicatorsOah2FHIR.fsh` states explicitly, leaf by leaf, that the code to use
is the plain field name -- e.g. the comment on `hydromorphological.morphology`
reads "where Observation.code is 'morphology'", on `water.dissolvedO2` reads
"...is 'dissolvedO2'", and so on. That is the convention these lookups follow:
**the OAH code equals the Python attribute name**, verbatim.

Two things worth knowing before trusting these codes against a terminology
server:

1. `oah-codeSystem.fsh` (`TemporaryOahSystem`) does NOT always define a
   matching code. Two known mismatches: `hydromorphological.morphology`'s
   ConceptMap-declared code `morphology` isn't in the code system, which
   instead defines `morophology` (a typo); `hydromorphological.landUse`'s
   declared code `landUse` isn't in the code system, which instead defines
   `LandUse` (capitalized). These are followed here because the ConceptMap
   -- the actual mapping spec -- says so explicitly; reconciling them with
   the code system is a fix that belongs in the `oah` IG repo itself.
2. Every `remote.*` leaf in `IndicatorsOah2FHIR.fsh` has its comment copied
   from `bioRisk.amphibians` and never updated -- all 29 of them literally
   say "where Observation.code is 'amphibians'". Taking that literally would
   tag every remote-sensing observation as amphibians, which is clearly a
   copy-paste bug, not an intended mapping. This module uses the same
   field-name convention the rest of the file demonstrates correctly instead
   of reproducing that bug.

`HealthIndicatorsOah2FHIR.fsh` does not restate "where Observation.code is
X" per leaf (its comments are absent), but its `display` value for every
element is quoted verbatim here, and the field-name-as-code convention is
applied by analogy with `IndicatorsOah2FHIR.fsh` for consistency across the IG.
"""

from __future__ import annotations

from typing import Dict

# --- HealthIndicatorsOah leaves -------------------------------------------
# code = field name; display copied verbatim from HealthIndicatorsOah2FHIR.fsh

DISEASE_PREVALENCE_DISPLAY: Dict[str, str] = {
    "highBloodPression": "% of people with high blood pressure (prevalence)",
    "hypertension": "% of people under treatment for hypertension",
    "highBloodPressionTreatment": "% of people under treatment for high blood pressure",
    "obesity": "% of people affected from obesity",
    "cholesterolemia190": "% of people with high total cholesterolemia (>=190 mg/dl)",
    "hypercholesterolemiaTreatment": "% of people under treatment for hypercholesterolemia",
    "cholesterolemia240": "% of people with high total cholesterolemia (>=240 mg/dl)",
    "diabetes": "% of people with high blood sugar/diabetes",
    "diabetesTreatment": "% of people under treatment for diabetes",
    "noPhysicalActivity": "% of people not engaging in physical activity",
    "cvd": "% of people affected from CVD",
    "gastrointestinal": "% of people with Cases of Gastrointestinal diseases",
    "longTermDisease": "% of people with long-term disease",
    "noLongTermDisease": "% of people without  long-term disease",
    "bmiBelow18": "% of people with BMI <18,5",
    "bmiBelow25": "% of people with BMI 18,5-24,9",
    "bmiBelow30": "% of people with BMI 25-29,9",
    "bmiAbove30": "% of people with BMI =>30",
    "diabateCopdCvd": "% of people that have or have had Diabetes, COPD or Cardiovascular disease",
    "noDiabateCopdCvd": "% of people that do not have Diabetes, COPD or Cardiovascular disease",
    "mentalHealth": "% of people experience with mental health issues",
    "borrelia": "% of people with Borrelia Burgdoferi",
    "campylobacter": "% of people with Campylobacter",
    "chlamydia": "% of people with Chlamydia Psittaci",
    "cryptosporidium": "% of people with Cryptosporidium",
    "entamoeba": "% of people with Entamoeba histolytica",
    "escherichiaColi": "% of people with Escherichia Coli",
    "giarda": "% of people with Giarda",
    "salmonella": "% of people with Salmonella",
    "yersiniaEnterocolitica": "% of people with Yersinia enterocolitica",
}

CAUSES_OF_DEATH_DISPLAY: Dict[str, str] = {
    "tbc": "% of deaths due to TBC",
    "viralHepatitis": "% of deaths due to Viral Hepatitis",
    "infectiveAndParasitic": "% of deaths due to infective and parasitic diseases",
    "bloodAndHematopoieticOrgans": "% of deaths due to diseases of the blood and hematopoietic organs",
    "diabetesMellitus": "% of deaths due to Diabetes Mellitus",
    "endocrineNutritionalMetabolic": "% of deaths due to endocrine, nutritional and metabolic diseases",
    "ischemicHeart": "% of deaths due to ischemic diseases of the heart",
    "otherHeart": "% of deaths due to other diseases of the heart",
    "otherCirculatorySystem": "% of deaths due to other diseases of the circulatory system",
    "pneumonia": "% of deaths due to Pneumonia",
    "chronicLowerRespiratory": "% of deaths due to chronic diseases of the lower respiratory tract",
    "otherRespiratorySystem": "% of deaths due to other diseases of the respiratory system",
    "SkinSubcutaneousTissue": "% of deaths due to diseases of the skin and subcutaneous tissue",
    "accidentalPoisoning": "% of deaths due to accidental poisoning",
    "malignantTumor": "% of deaths due to Malignant Tumors",
    "healthcareSensitiveCauses": "% of deaths due to Healthcare-Sensitive Causes",
    "winterExcess": "% of Excess Mortality in Winter",
    "all": "% of deaths due to all causes",
    "cancer": "% of deaths due to cancer",
    "diabetes": "% of deaths due to diabetes",
    "cardiovascular": "% of deaths due to cardiovascular disease",
    "respiratory": "% of deaths due to respiratory disease",
    "COPDLungCancer": "% of deaths due to COPD and lung cancer",
}

HOSPITALIZATION_DISPLAY: Dict[str, str] = {
    "diabetesMellitus": "% of hospitalizations due to Diabetes Mellitus",
    "malignantTumor": "% of hospitalizations due to malignant tumors",
    "hypertension": "% of hospitalizations due to Hypertension",
    "cardiovascular": "% of hospitalizations due to Circulatory System Diseases",
    "respiratory": "% of hospitalizations due to respiratory diseases",
    "asthma": "% of hospitalizations for Asthma",
    "avoidablePrimaryPrevention": "% of hospitalizations avoidable by primary prevention",
}

# --- IndicatorsOah `Base`-typed leaves -------------------------------------
# code = field name; display copied from the `short`/description text in
# IndicatorsOah.fsh itself.

HYDROMORPHOLOGICAL_DISPLAY: Dict[str, str] = {
    "morphology": "Morphology of the streams",
    "hydrology": "Hydrology of the stream",
    "landUse": "Land use in the margins",
}

WATER_DISPLAY: Dict[str, str] = {
    "nutrients": "Nutrients",
    "pH": "pH",
    "dissolvedO2": "Dissolved O2",
    "waterTemperature": "Water temperature",
    "tds": "Total dissolved solids (TDS)",
    "tss": "Total suspended solids (TSS)",
    "conductivity": "Conductivity",
    "pharmaceuticals": "Pharmaceuticals",
    "foam": "Foam/colour/smell",
    "coliforms": "Coliforms",
}

BIO_RISK_DISPLAY: Dict[str, str] = {
    "diptera": "Diptera",
    "ticks": "Ticks",
    "invasiveOrganisms": "Invasive invertebrate, plants and fish",
    "birds": "Birds",
    "diatomTratology": "Diatom teratology",
    "fish": "Fish",
    "amphibians": "Amphibians",
}

REMOTE_SENSING_DISPLAY: Dict[str, str] = {
    "ndci": "Normalized Difference Chlorophyll Index (NDCI)",
    "mci": "Maximum Chlorophyll Index (MCI)",
    "bwdrvi": "Blue Wide Dynamic Range Vegetation Index (BWDRVI)",
    "evi": "Enhanced Vegetation Index (EVI)",
    "evi2": "Enhanced Vegetation Index 2 (EVI2)",
    "ndvi": "Normalized Difference Vegetation Index (NDVI)",
    "mndvi": "Modified Normalized Difference Vegetation Index (mNDVI)",
    "ndwi": "Normalized Difference Water Index (NDWI)",
    "savi": "Soil Adjusted Vegetation Index (SAVI)",
    "tsavi": "Transformed Soil Adjusted Vegetation Index (TSAVI)",
    "lwci": "Leaf Water Content Index (LWCI)",
    "gvmi": "Global Vegetation Moisture Index (GVMI)",
    "gemi": "Global Environment Monitoring Index (GEMI)",
    "lai": "Leaf Area Index (LAI)",
    "glai": "Green Leaf Area Index (GLAI)",
    "fapar": "Fraction of Absorbed Photosynthetically Active Radiation (FAPAR)",
    "mndwi": "Modified Normalized Difference Water Index (MNDWI)",
    "andwi": "Augmented Normalized Difference Water Index (ANDWI)",
    "s2wi": "Sentinel-2 Water Index (S2WI)",
    "lswi": "Land Surface Water Index (LSWI)",
    "ndviMndwiModel": "NDVI-MNDWI Model",
    "lst": "Land Surface Temperature (LST)",
    "blfei": "Built-Up Land Features Extraction Index (BLFEI)",
    "brba": "Band Ratio for Built-up Area (BRBA)",
    "nbai": "Normalized Built-up Area Index (NBAI)",
    "ibi": "Index-Based Built-Up Index (IBI)",
    "ebbi": "Enhanced Built-Up and Bareness Index (EBBI)",
    "pisi": "Perpendicular Impervious Surface Index (PISI)",
    "ui": "Urban Index (UI)",
    "vibi": "Vegetation Index Built-up Index (VIBI)",
}

BIOLOGICAL_MICROBIOMES_DISPLAY = "Microbiomes/Biofilms"
