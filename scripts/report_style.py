"""Shared look of the report's figures: colours, type and sizes.

Used by ``build_report_diagrams.py`` (hand-laid-out SVG schematics) and
``build_report_figures.py`` (matplotlib charts) so that one colour means the same thing in
every figure of the report.

Colour roles (hex values from the reference palette of the charting guide the project uses;
the three categorical hues pass its colour-vision checks pairwise, and blue against red too):

- BLUE    the trusted base and the evidence-bound guard; messages that describe; "supported"
- ORANGE  messages that list the legal writes
- AQUA    messages built from the planner's own rejected plan
- RED     the attacker and unsafe effects; "not supported"
- GREY    reference conditions and anything that is context, not the subject

Text is always set in the ink colours, never in a series colour.
"""
from __future__ import annotations

BLUE = '#257de0'
ORANGE = '#f47230'
AQUA = '#00b894'
RED = '#dc3c3d'
GREY = '#9a9a9a'

BLUE_DARK = '#1757ac'      # outline of trusted parts
BLUE_TINT = '#eaf2fd'      # fill of trusted parts
BLUE_WASH = '#f4f8fe'      # background of the trusted region
ORANGE_TINT = '#fdebe1'
AQUA_TINT = '#dff5ef'
RED_TINT = '#fbe6e6'
GREY_TINT = '#f3f3f3'      # fill of untrusted parts
GREY_WASH = '#f8f8f7'      # background of the untrusted region
GREY_LINE = '#8c8c8c'      # outline of untrusted parts

INK = '#191919'
INK_2 = '#555555'
GRID = '#e7e7e7'
AXIS = '#c2c2c2'
SURFACE = '#ffffff'

# Arial metrics. Liberation Sans is metric-compatible and is what the build machines have.
FONT_FAMILY = ['Arial', 'Liberation Sans', 'Helvetica', 'DejaVu Sans']
SVG_FONT = "Arial, 'Liberation Sans', Helvetica, sans-serif"

# Widths of the IEEE two-column page (A4): one column and the full text width, in millimetres.
COLUMN_MM = 88.9
PAGE_MM = 182.0
MM_PER_INCH = 25.4

# The three groups of refusal messages, in the order of the ladder.
GROUP_COLOUR = {'describe': BLUE, 'list': ORANGE, 'plan': AQUA, 'reference': GREY}
GROUP_TINT = {'describe': BLUE_TINT, 'list': ORANGE_TINT, 'plan': AQUA_TINT, 'reference': GREY_TINT}
