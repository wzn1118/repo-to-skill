# ADR 0002: Standard-Library Bootstrap

Status: accepted

The formal runtime remains Python 3.12 with Pydantic and Typer. The first slice is also compatible
with the available Python 3.10 standard library so restricted environments can test core behavior.
Migration to Pydantic models must preserve emitted schema and canonical JSON compatibility.
