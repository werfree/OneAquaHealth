"""OAH Data Set model.

Source: oah/input/fsh/model-maps/DataSetOah.fsh
Maps to (via DataSetOah2FHIR.fsh): LibraryOah, Attachment, DataRequirement.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .common import CodeableConcept, ContactDetail, Quantity


class DataSetRecord(BaseModel):
    """`DataSet.record` (0..*) -- one file/record within the data set."""

    title: Optional[str] = None
    format: Optional[str] = None
    link: Optional[str] = None
    size: Optional[Quantity] = None


class DataSetOah(BaseModel):
    """OAH Data Set: metadata, stewardship and composition of a published data set."""

    pid: str = Field(..., description="1..1. Globally unique, persistent, resolvable identifier (url).")
    title: Optional[str] = Field(None, description="0..1. Data set title.")
    description: List[str] = Field(default_factory=list, description="0..*. Data set description.")
    version: Optional[str] = Field(None, description="0..1. Data set version.")
    type: Optional[CodeableConcept] = Field(None, description="0..1. Type of data set.")
    contact: List[ContactDetail] = Field(default_factory=list, description="0..*. Contact details.")
    publisher: Optional[str] = Field(None, description="0..1. Data set publisher.")
    author: List[ContactDetail] = Field(default_factory=list, description="0..*. Data set author(s).")
    date: Optional[datetime] = Field(None, description="0..1. Date the data set was last significantly changed.")
    dateOfApproval: Optional[datetime] = Field(None, description="0..1. Date the publisher approved the data set.")
    dateOfReview: Optional[datetime] = Field(None, description="0..1. Date of last periodic review.")
    copyright: List[str] = Field(default_factory=list, description="0..*. Copyright statement(s).")
    size: Optional[Quantity] = Field(None, description="0..1. Overall data set size (e.g. MB).")
    numberOfRecords: Optional[int] = Field(None, description="0..1. Number of records in the data set.")
    record: List[DataSetRecord] = Field(default_factory=list, description="0..*. Individual records/files.")
