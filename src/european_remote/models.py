"""Job advertisement Pydantic models.

:Description: Defines Pydantic models for job advertisement data structures
:Classes:
    - ``Compensation`` -- pay range and benefits
    - ``Qualifications`` -- required and additional qualifications
    - ``JobAdvertisement`` -- complete job posting details
"""
from datetime import date
from pydantic import BaseModel, Field
from typing import Optional, Union, Dict, List


class Compensation(BaseModel):
    """A description of the compensation model of a job advertisement"""
    pay_range: Optional[Union[str, Dict]] = Field(
        default=None,
        description="The pay range for the position in Europe, or in Spain, whichever is the most specific."
    )
    benefits: Optional[List[str]] = Field(
        default_factory=list,
        description="List of individual benefits identified and their respective conditions, if any."
    )


class Qualifications(BaseModel):
    """A collection of qualifications required from a canditate to a job"""
    required: Optional[List[str]] = Field(
        default_factory=list,
        description="a list of individual qualifications required from a candidate to a job"
    )
    additional: Optional[List[str]] = Field(
        default_factory=list,
        description="a list of individual additional qualifications identified within the job ad"
    )


class JobAdvertisement(BaseModel):
    """A job posting with details"""
    company_name: Optional[str] = Field(description="the company posting the job advertisement")
    department_name: Optional[str] = Field(description="the name of the department where the job opening sits")
    team_name: Optional[str] = Field(description="the name of the team where the job opening is")
    date_posted: Optional[date] = Field(description="the date in which the job opening was first posted")
    job_context: Optional[str] = Field(
        description="job context: information about the business, the team, and the project for this job opening")
    compensation: Optional[Compensation]
    responsibilities: Optional[List[str]]
    qualifications: Optional[Qualifications]
