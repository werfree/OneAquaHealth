"""OAH Health Indicators model.

Source: oah/input/fsh/model-maps/HealthIndicatorsOah.fsh
Maps to (via HealthIndicatorsOah2FHIR.fsh): observation-health-measure-oah.

Each leaf below is a repeating `HealthMeasureOah` (0..*), grouped under one of
three per-district/per-population bundles: disease prevalence, causes of
death, hospitalizations. Field names mirror the FSH element names exactly
(including the inconsistent capitalization on `SkinSubcutaneousTissue` and
`COPDLungCancer`, kept for fidelity with the source model).
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .health_measure import HealthMeasureOah


class DiseasePrevalenceGroup(BaseModel):
    """`HealthIndicatorsOah.diseasePrevalence` -- prevalence indicators for one population/district."""

    highBloodPression: List[HealthMeasureOah] = Field(default_factory=list)
    hypertension: List[HealthMeasureOah] = Field(default_factory=list)
    highBloodPressionTreatment: List[HealthMeasureOah] = Field(default_factory=list)
    obesity: List[HealthMeasureOah] = Field(default_factory=list)
    cholesterolemia190: List[HealthMeasureOah] = Field(default_factory=list, description=">=190 mg/dl.")
    hypercholesterolemiaTreatment: List[HealthMeasureOah] = Field(default_factory=list)
    cholesterolemia240: List[HealthMeasureOah] = Field(default_factory=list, description=">=240 mg/dl.")
    diabetes: List[HealthMeasureOah] = Field(default_factory=list)
    diabetesTreatment: List[HealthMeasureOah] = Field(default_factory=list)
    noPhysicalActivity: List[HealthMeasureOah] = Field(default_factory=list)
    cvd: List[HealthMeasureOah] = Field(default_factory=list)
    gastrointestinal: List[HealthMeasureOah] = Field(default_factory=list)
    longTermDisease: List[HealthMeasureOah] = Field(default_factory=list)
    noLongTermDisease: List[HealthMeasureOah] = Field(default_factory=list)
    bmiBelow18: List[HealthMeasureOah] = Field(default_factory=list, description="BMI < 18.5.")
    bmiBelow25: List[HealthMeasureOah] = Field(default_factory=list, description="BMI 18.5-24.9.")
    bmiBelow30: List[HealthMeasureOah] = Field(default_factory=list, description="BMI 25-29.9.")
    bmiAbove30: List[HealthMeasureOah] = Field(default_factory=list, description="BMI >= 30.")
    diabateCopdCvd: List[HealthMeasureOah] = Field(default_factory=list, description="Diabetes, COPD or CVD (has/had).")
    noDiabateCopdCvd: List[HealthMeasureOah] = Field(default_factory=list, description="No Diabetes, COPD or CVD.")
    mentalHealth: List[HealthMeasureOah] = Field(default_factory=list)
    borrelia: List[HealthMeasureOah] = Field(default_factory=list, description="Borrelia burgdorferi.")
    campylobacter: List[HealthMeasureOah] = Field(default_factory=list)
    chlamydia: List[HealthMeasureOah] = Field(default_factory=list, description="Chlamydia psittaci.")
    cryptosporidium: List[HealthMeasureOah] = Field(default_factory=list)
    entamoeba: List[HealthMeasureOah] = Field(default_factory=list, description="Entamoeba histolytica.")
    escherichiaColi: List[HealthMeasureOah] = Field(default_factory=list)
    giarda: List[HealthMeasureOah] = Field(default_factory=list)
    salmonella: List[HealthMeasureOah] = Field(default_factory=list)
    yersiniaEnterocolitica: List[HealthMeasureOah] = Field(default_factory=list)


class CausesOfDeathGroup(BaseModel):
    """`HealthIndicatorsOah.causesOfDeath` -- mortality indicators for one population/district."""

    tbc: List[HealthMeasureOah] = Field(default_factory=list)
    viralHepatitis: List[HealthMeasureOah] = Field(default_factory=list)
    infectiveAndParasitic: List[HealthMeasureOah] = Field(default_factory=list)
    bloodAndHematopoieticOrgans: List[HealthMeasureOah] = Field(default_factory=list)
    diabetesMellitus: List[HealthMeasureOah] = Field(default_factory=list)
    endocrineNutritionalMetabolic: List[HealthMeasureOah] = Field(default_factory=list)
    ischemicHeart: List[HealthMeasureOah] = Field(default_factory=list)
    otherHeart: List[HealthMeasureOah] = Field(default_factory=list)
    otherCirculatorySystem: List[HealthMeasureOah] = Field(default_factory=list)
    pneumonia: List[HealthMeasureOah] = Field(default_factory=list)
    chronicLowerRespiratory: List[HealthMeasureOah] = Field(default_factory=list)
    otherRespiratorySystem: List[HealthMeasureOah] = Field(default_factory=list)
    SkinSubcutaneousTissue: List[HealthMeasureOah] = Field(default_factory=list)  # sic, matches source FSH
    accidentalPoisoning: List[HealthMeasureOah] = Field(default_factory=list)
    malignantTumor: List[HealthMeasureOah] = Field(default_factory=list)
    healthcareSensitiveCauses: List[HealthMeasureOah] = Field(default_factory=list)
    winterExcess: List[HealthMeasureOah] = Field(default_factory=list, description="Excess mortality in winter.")
    all: List[HealthMeasureOah] = Field(default_factory=list, description="All causes.")
    cancer: List[HealthMeasureOah] = Field(default_factory=list)
    diabetes: List[HealthMeasureOah] = Field(default_factory=list)
    cardiovascular: List[HealthMeasureOah] = Field(default_factory=list)
    respiratory: List[HealthMeasureOah] = Field(default_factory=list)
    COPDLungCancer: List[HealthMeasureOah] = Field(default_factory=list)  # sic, matches source FSH


class HospitalizationGroup(BaseModel):
    """`HealthIndicatorsOah.hospitalization` -- hospitalization indicators for one population/district."""

    diabetesMellitus: List[HealthMeasureOah] = Field(default_factory=list)
    malignantTumor: List[HealthMeasureOah] = Field(default_factory=list)
    hypertension: List[HealthMeasureOah] = Field(default_factory=list)
    cardiovascular: List[HealthMeasureOah] = Field(default_factory=list, description="Circulatory system diseases.")
    respiratory: List[HealthMeasureOah] = Field(default_factory=list)
    asthma: List[HealthMeasureOah] = Field(default_factory=list)
    avoidablePrimaryPrevention: List[HealthMeasureOah] = Field(default_factory=list)


class HealthIndicatorsOah(BaseModel):
    """OAH Health Indicators: health and wellness prevalence indicators for a population."""

    diseasePrevalence: List[DiseasePrevalenceGroup] = Field(default_factory=list)
    causesOfDeath: List[CausesOfDeathGroup] = Field(default_factory=list)
    hospitalization: List[HospitalizationGroup] = Field(default_factory=list)
